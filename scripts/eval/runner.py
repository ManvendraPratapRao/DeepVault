"""
eval/runner.py
==============
Multi-model evaluation engine for DeepVault RAG.
Runs the golden dataset through the RAG pipeline and computes Custom Retrieval + Ragas Metrics.
"""

import asyncio
import logging
import statistics

from datasets import Dataset
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from tqdm import tqdm

from app.config import settings
from app.core.models.query import QueryRequest, QueryResponse
from app.dependencies import get_reranker, get_retriever, initialize_all, shutdown_all
from app.infrastructure.llm.groq import GroqLLMClient
from app.services.query import QueryService

from .config import (
    DEFAULT_LIMIT,
    DEFAULT_RPM,
    EVAL_TEMPERATURE,
    GENERATOR_POOL,
    GROQ_PRICING,
    JUDGE_POOL,
    EvalRunConfig,
    ModelRotator,
)
from .golden_qa import load_golden_dataset
from .ragas_adapter import to_ragas_row
from .report import save_report

logger = logging.getLogger(__name__)


def calculate_retrieval_metrics(response: QueryResponse, ground_truth_source: str, k: int = 5) -> dict:
    """Calculates Hit@K, MRR, Precision@K, and Recall@K based on the source document."""
    sources = [chunk.metadata.get("source") for chunk in response.sources][:k]

    # Strip '.md' extension for robust matching between chunk metadata and golden dataset
    hits = [1 if str(src).replace(".md", "") == str(ground_truth_source).replace(".md", "") else 0 for src in sources]

    hit_rate = 1.0 if sum(hits) > 0 else 0.0

    mrr = 0.0
    for i, hit in enumerate(hits):
        if hit == 1:
            mrr = 1.0 / (i + 1)
            break

    precision_k = sum(hits) / k if k > 0 else 0.0
    recall_k = 1.0 if hit_rate > 0 else 0.0  # Binary recall since we usually have 1 source doc per question

    return {"hit_rate_at_k": hit_rate, "mrr": mrr, "precision_at_k": precision_k, "recall_at_k": recall_k}


async def run_evaluation(config: EvalRunConfig, initial_results: dict = None):
    # 1. Initialize System & Override Settings for Eval
    settings.LLM_TEMPERATURE = EVAL_TEMPERATURE
    settings.CACHE_ENABLED = False  # Disable cache to measure raw latency!
    await initialize_all()

    dataset = load_golden_dataset(limit=config.limit)
    gen_rotator = ModelRotator(GENERATOR_POOL)
    judge_rotator = ModelRotator(JUDGE_POOL)

    combinations = config.combinations()
    logger.info(f"Starting eval for {len(combinations)} combinations. Sample size: {len(dataset)} per combo.")

    results_summary = initial_results or {}

    for chunk_strat, retr_strat in combinations:
        combo_key = config.strategy_key(chunk_strat, retr_strat)
        if combo_key in results_summary:
            logger.info(f"Skipping {combo_key} - already evaluated in checkpoint.")
            continue

        logger.info(f"==> Evaluating: {chunk_strat} + {retr_strat}")

        # Override settings for this run
        settings.CHUNKER_STRATEGY = chunk_strat
        settings.RETRIEVAL_STRATEGY = retr_strat

        # Build custom query service for this combination
        retriever = await get_retriever(strategy=retr_strat)
        # We manually instantiate LLMClient to easily hot-swap the model
        llm_client = GroqLLMClient()
        reranker = await get_reranker() if "rerank" in retr_strat else None

        query_service = QueryService(
            retriever=retriever,
            llm_client=llm_client,
            cache_service=None,  # cache disabled
            reranker=reranker,
            llm_router=None,  # disable router to force the rotated model
        )

        ragas_rows = []
        retrieval_stats = {"hit_rate": 0, "mrr": 0, "precision": 0, "cost": 0.0}
        latencies = []

        for idx, qa in enumerate(tqdm(dataset, desc=f"{chunk_strat}+{retr_strat}")):
            model_name = gen_rotator.get_next()
            settings.GROQ_MODEL_NAME = model_name.replace("groq/", "")  # Force the model (strip prefix for native SDK)

            req = QueryRequest(
                query_text=qa.question,
                chunking_strategy=chunk_strat,
                retrieval_strategy=retr_strat,
                top_k=config.top_k,
                use_query_rewriting=("_rewrite" in retr_strat),
                model_name=model_name.replace("groq/", ""),
            )

            try:
                response = await query_service.ask(req, request_id=f"eval_{idx}")

                # Custom Retrieval Metrics
                ret_metrics = calculate_retrieval_metrics(response, qa.source_document, k=config.top_k)
                retrieval_stats["hit_rate"] += ret_metrics["hit_rate_at_k"]
                retrieval_stats["mrr"] += ret_metrics["mrr"]
                retrieval_stats["precision"] += ret_metrics["precision_at_k"]
                latencies.append(response.latency_ms)

                # Cost Calculation
                pricing = GROQ_PRICING.get(model_name, GROQ_PRICING["default"])
                cost = (response.usage.prompt_tokens / 1_000_000 * pricing["input"]) + (
                    response.usage.completion_tokens / 1_000_000 * pricing["output"]
                )
                retrieval_stats["cost"] += cost

                # Prepare for Ragas
                ragas_rows.append(to_ragas_row(qa.question, response, qa.answer))

            except Exception as e:
                logger.error(f"Eval query failed: {e}")

            # Strict Rate Limiter to respect TPM/RPM
            if config.rpm > 0:
                await asyncio.sleep(60.0 / config.rpm)

        # Average custom metrics
        n = len(ragas_rows)
        if n > 0:
            retrieval_stats["hit_rate"] /= n
            retrieval_stats["mrr"] /= n
            retrieval_stats["precision"] /= n

        if latencies:
            # Calculate percentiles (n=100 for percentiles)
            try:
                quantiles = statistics.quantiles(latencies, n=100)
                retrieval_stats["latency_p50_ms"] = quantiles[49]  # Median
                retrieval_stats["latency_p95_ms"] = quantiles[94]
                retrieval_stats["latency_p99_ms"] = quantiles[98]
            except statistics.StatisticsError:
                # Fallback if too few data points for quantiles
                retrieval_stats["latency_p50_ms"] = statistics.median(latencies)
                retrieval_stats["latency_p95_ms"] = max(latencies)
                retrieval_stats["latency_p99_ms"] = max(latencies)

            retrieval_stats["latency_mean_ms"] = statistics.mean(latencies)
        else:
            retrieval_stats["latency_p50_ms"] = 0
            retrieval_stats["latency_p95_ms"] = 0
            retrieval_stats["latency_p99_ms"] = 0
            retrieval_stats["latency_mean_ms"] = 0

        # Run Ragas Evaluation
        # We wrap the ChatGroq model with Ragas LangchainLLMWrapper
        judge_model_name = judge_rotator.get_next()
        # strip 'groq/' prefix for langchain
        clean_model_name = judge_model_name.replace("groq/", "")

        chat_model = ChatGroq(model_name=clean_model_name, api_key=settings.GROQ_API_KEY, temperature=EVAL_TEMPERATURE)
        ragas_llm = LangchainLLMWrapper(chat_model)

        logger.info(f"Running Ragas with judge: {judge_model_name} on {n} responses...")
        hf_dataset = Dataset.from_list(ragas_rows)

        # Initialize Embeddings for Ragas metrics that require embeddings (e.g. answer_relevancy)
        hf_embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        ragas_embeddings = LangchainEmbeddingsWrapper(hf_embeddings)

        if len(hf_dataset) > 0:
            ragas_result = evaluate(
                dataset=hf_dataset,
                metrics=[
                    context_precision,
                    context_recall,
                    faithfulness,
                    answer_relevancy,
                    answer_correctness,
                ],
                llm=ragas_llm,
                embeddings=ragas_embeddings,
            )

            # Convert Ragas EvaluationResult to a standard dictionary of means for JSON serialization
            try:
                df = ragas_result.to_pandas()
                # Select only numeric columns to average (e.g., faithfulness, answer_relevancy)
                numeric_df = df.select_dtypes(include=["number"])
                ragas_dict = numeric_df.mean().to_dict()
            except Exception as e:
                logger.error(f"Failed to extract Ragas means: {e}")
                ragas_dict = {}

            results_summary[combo_key] = {
                "custom_retrieval": retrieval_stats,
                "ragas": ragas_dict,
            }
            logger.info(f"Ragas results for {combo_key}: {ragas_dict}")

            # Save Report incrementally (Checkpoint)
            save_report(config.run_id, results_summary)

    logger.info("Evaluation fully completed.")
    await shutdown_all()


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=str, required=True)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--rpm", type=int, default=DEFAULT_RPM)
    args = parser.parse_args()

    config = EvalRunConfig(run_id=args.run_id, limit=args.limit, rpm=args.rpm)

    # Load existing checkpoint if it exists
    run_dir = Path("data/eval_runs") / config.run_id
    summary_path = run_dir / "summary.json"
    results_summary = {}

    if summary_path.exists():
        try:
            with open(summary_path, encoding="utf-8") as f:
                results_summary = json.load(f)
            logger.info(f"Loaded existing checkpoint with {len(results_summary)} completed strategies. Resuming...")
        except Exception as e:
            logger.warning(f"Could not load checkpoint {summary_path}: {e}")

    asyncio.run(run_evaluation(config, results_summary))
