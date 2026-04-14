import argparse
import asyncio
import json

# Add project root to path
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.append(os.getcwd())

import numpy as np

from app.core.models.query import QueryRequest
from app.dependencies import get_query_service, initialize_all
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.logging.structured import logger
from app.prompts.v1 import JUDGE_FAITHFULNESS_PROMPT, JUDGE_RELEVANCE_PROMPT

# Storage structure
EVAL_RUNS_DIR = Path("data/eval_runs")

# Judging Settings
FAITH_MODEL = "llama-3.1-8b-instant"
REL_MODEL = "llama-3.1-8b-instant"
RPM_LIMIT = 25  # Safe limit under 30RPM cap

# Pricing per million tokens (Groq API as of current specs)
PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}


class AsyncRateLimiter:
    """Token Bucket-ish limiter for API pacing."""

    def __init__(self, rpm: int):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.perf_counter()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                delay = self.interval - elapsed
                await asyncio.sleep(delay)
            self.last_call = time.perf_counter()


class EvalEngine:
    def __init__(self, chunking_strategies=None, retrieval_strategies=None, dry_run=False):
        self.query_service = None  # Latent init
        self.judge_client = GroqLLMClient()
        self.limiter = AsyncRateLimiter(RPM_LIMIT)
        self.embedder = BgeEmbedder()
        self.chunking_strategies = chunking_strategies or ["fixed", "sliding", "structure", "semantic"]
        self.retrieval_strategies = retrieval_strategies or ["vector"]
        self.dry_run = dry_run
        self.session_tokens = 0

    async def initialize(self):
        if not self.dry_run:
            await initialize_all()
            self.query_service = await get_query_service()

    def _load_questions(self) -> list[dict[str, Any]]:
        research_file = Path("data/research_papers_golden_qa.json")
        synthetic_file = Path("synthetic_data_v2/golden_qa_dataset.json")

        all_q = []
        if research_file.exists():
            with open(research_file) as f:
                data = json.load(f)
                for item in data:
                    all_q.append({**item, "category": "research"})

        if synthetic_file.exists():
            with open(synthetic_file) as f:
                data = json.load(f)
                for item in data:
                    all_q.append({**item, "category": "synthetic"})

        return all_q

    def _get_balanced_sample(self, questions: list[dict[str, Any]], total_limit: int = 250) -> list[dict[str, Any]]:
        research_q = [q for q in questions if q["category"] == "research"]
        synthetic_q = [q for q in questions if q["category"] == "synthetic"]

        # Determine splits: 60% synthetic, 40% research
        s_limit = int(total_limit * 0.6)
        r_limit = total_limit - s_limit

        s_sample = random.sample(synthetic_q, min(s_limit, len(synthetic_q)))
        r_sample = random.sample(research_q, min(r_limit, len(research_q)))

        # If we didn't get enough of one, fill with the other
        if len(s_sample) < s_limit:
            r_sample.extend(
                random.sample(
                    [q for q in research_q if q not in r_sample],
                    min(s_limit - len(s_sample), len(research_q) - len(r_sample)),
                )
            )
        elif len(r_sample) < r_limit:
            s_sample.extend(
                random.sample(
                    [q for q in synthetic_q if q not in s_sample],
                    min(r_limit - len(r_sample), len(synthetic_q) - len(s_sample)),
                )
            )

        sample = r_sample + s_sample
        random.shuffle(sample)
        return sample

    def _parse_judge_json(self, raw_response: str) -> dict[str, Any]:
        try:
            clean_str = re.sub(r"```json\s*|\s*```", "", raw_response).strip()
            return json.loads(clean_str)
        except Exception:
            return {"score": 3, "reasoning": "Failed to parse judge response."}

    def _cosine_similarity(self, vec1, vec2):
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        if model not in PRICING:
            return 0.0
        rates = PRICING[model]
        return (prompt_tokens * rates["input"] + completion_tokens * rates["output"]) / 1_000_000

    async def _evaluate_answer(self, question: str, answer: str, context: str, ground_truth: str):
        # Limit context to ~1200 characters to save tokens
        truncated_context = context[:1200]

        # 1. Faithfulness
        await self.limiter.wait()
        self.judge_client.model = FAITH_MODEL
        faith_prompt = JUDGE_FAITHFULNESS_PROMPT.format(context=truncated_context, answer=answer)
        faith_res = await self.judge_client.generate(faith_prompt)
        faith_eval = self._parse_judge_json(faith_res.answer)
        self.session_tokens += faith_res.usage.total_tokens

        faith_pt = faith_res.usage.prompt_tokens
        faith_ct = faith_res.usage.completion_tokens

        # 2. Relevance
        await self.limiter.wait()
        self.judge_client.model = REL_MODEL
        rel_prompt = JUDGE_RELEVANCE_PROMPT.format(question=question, answer=answer)
        rel_res = await self.judge_client.generate(rel_prompt)
        rel_eval = self._parse_judge_json(rel_res.answer)
        self.session_tokens += rel_res.usage.total_tokens

        rel_pt = rel_res.usage.prompt_tokens
        rel_ct = rel_res.usage.completion_tokens

        # 3. Semantic Similarity
        v1 = await self.embedder.embed_text(answer)
        v2 = await self.embedder.embed_text(ground_truth)
        sim = float(self._cosine_similarity(v1, v2))

        return {
            "faithfulness": faith_eval.get("score", 3),
            "faithfulness_reasoning": faith_eval.get("reasoning", ""),
            "relevance": rel_eval.get("score", 3),
            "relevance_reasoning": rel_eval.get("reasoning", ""),
            "similarity": sim,
            "hallucination": 1 if faith_eval.get("score", 3) <= 2 else 0,
            "judge_models": {"faith": FAITH_MODEL, "rel": REL_MODEL},
            "judge_prompt_tokens": faith_pt + rel_pt,
            "judge_completion_tokens": faith_ct + rel_ct,
            "cost_usd": self._calculate_cost(faith_pt, faith_ct, FAITH_MODEL)
            + self._calculate_cost(rel_pt, rel_ct, REL_MODEL),
        }

    def _update_progress(self, run_dir: Path, step_data: dict):
        with open(run_dir / "progress.json", "w") as f:
            json.dump(step_data, f)

        # Update token usage metric as well
        with open(run_dir / "token_usage.json", "w") as f:
            json.dump({"total_session_tokens": self.session_tokens, "last_updated": datetime.now().isoformat()}, f)

    def _write_summary(self, run_id: str, run_dir: Path, results: dict):
        summary = {"run_id": run_id, "by_chunking_strategy": {}}

        for key, logs in results.items():
            if not logs:
                continue

            chunking = logs[0]["chunking_strategy"]
            n = len(logs)
            total_cost = sum(r["cost_usd"] for r in logs)

            # Simple averages
            avg = lambda k: sum(r.get(k, 0) for r in logs) / n

            # Calculate cost per 1k queries
            cost_cents_1k = (total_cost / n) * 1000 * 100 if n > 0 else 0

            # Efficiency index -> faithfulness / cost
            faith = avg("faithfulness")
            eff = faith / cost_cents_1k if cost_cents_1k > 0 else 0

            # Category breakdown
            res_logs = [r for r in logs if r.get("category") == "research"]
            syn_logs = [r for r in logs if r.get("category") == "synthetic"]

            res_faith = sum(r.get("faithfulness", 0) for r in res_logs) / len(res_logs) if res_logs else 0
            syn_faith = sum(r.get("faithfulness", 0) for r in syn_logs) / len(syn_logs) if syn_logs else 0

            summary["by_chunking_strategy"][chunking] = {
                "hit_rate": avg("hit"),
                "p_at_k": avg("precision_at_k"),
                "context_precision_at_1": avg("context_precision_at_1"),
                "faithfulness": faith,
                "relevance": avg("relevance"),
                "similarity": avg("similarity"),
                "hallucination_rate": avg("hallucination"),
                "p95_latency_ms": np.percentile([r["latency_ms"] for r in logs], 95) if logs else 0,
                "total_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in logs),
                "total_cost_usd": total_cost,
                "cost_cents_per_1k_queries": cost_cents_1k,
                "efficiency_index": eff,
                "research_faithfulness": res_faith,
                "synthetic_faithfulness": syn_faith,
                "n_evaluated": n,
            }

        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        # Update run index
        index_file = EVAL_RUNS_DIR / "runs_index.json"
        index = {}
        if index_file.exists():
            with open(index_file) as f:
                index = json.load(f)

        index[run_id] = {
            "timestamp": datetime.now().isoformat(),
            "retrieval_strategies": self.retrieval_strategies,
            "chunking_strategies": self.chunking_strategies,
            "total_questions": sum(len(x) for x in results.values()),
        }
        with open(index_file, "w") as f:
            json.dump(index, f, indent=2)

    async def run_benchmark(self, limit: int = 50, runs: int = 1):
        if self.dry_run:
            print(
                f"\n[DRY RUN] Would evaluate {limit} questions across {len(self.chunking_strategies)} chunking strategies."
            )
            print(f"Total calls: {limit * len(self.chunking_strategies) * len(self.retrieval_strategies)}")
            print("To proceed, remove the --dry-run flag.")
            return

        await self.initialize()
        questions = self._load_questions()
        if not questions:
            logger.error("No questions found in dataset!")
            return

        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{run_ts}"

        # Support multiple retrieval strategies in different folders (usually just one per run though)
        run_dirs = {}
        for r_strat in self.retrieval_strategies:
            r_dir = EVAL_RUNS_DIR / r_strat / run_id
            r_dir.mkdir(parents=True, exist_ok=True)
            run_dirs[r_strat] = r_dir

            config_data = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "retrieval_strategy": r_strat,
                "chunking_strategies": self.chunking_strategies,
                "questions_per_strategy": limit,
                "judge_faith_model": FAITH_MODEL,
                "judge_rel_model": REL_MODEL,
                "top_k": 5,
            }
            with open(r_dir / "config.json", "w") as f:
                json.dump(config_data, f, indent=2)

        strategy_keys = [f"{c}_{r}" for c in self.chunking_strategies for r in self.retrieval_strategies]

        overall_results = {s: [] for s in strategy_keys}
        total_steps = len(strategy_keys) * runs * limit
        current_step = 0

        for run_idx in range(runs):
            sample = self._get_balanced_sample(questions, total_limit=limit)

            for c_strat in self.chunking_strategies:
                for r_strat in self.retrieval_strategies:
                    strategy_key = f"{c_strat}_{r_strat}"
                    run_dir = run_dirs[r_strat]

                    print(f"\n[START] Strategy Pass: {strategy_key} (Run {run_idx + 1}/{runs})")

                    for q_idx, q_item in enumerate(sample):
                        try:
                            print(
                                f"  [{strategy_key}] Q {q_idx + 1}/{limit}: {q_item['question'][:50]}...",
                                end=" ",
                                flush=True,
                            )

                            await self.limiter.wait()  # Cap requests

                            start_time = time.perf_counter()
                            req = QueryRequest(
                                query_text=q_item["question"],
                                chunking_strategy=c_strat,
                                retrieval_strategy=r_strat,
                                top_k=5,
                            )
                            resp = await self.query_service.ask(req)
                            latency = (time.perf_counter() - start_time) * 1000

                            # 1. Retrieval Analysis (P@k, R@k, CP@1)
                            retrieved_docs_raw = [c.metadata.get("source", "").lower() for c in resp.sources]

                            # Clean punctuation from retrieved sources and target doc for matching
                            clean = lambda text: re.sub(r"[^a-z0-9]", "", str(text).lower())

                            retrieved_docs = [clean(d) for d in retrieved_docs_raw]
                            target_doc = clean(q_item["source_document"])

                            hits = sum(1 for d in retrieved_docs if target_doc in d or d in target_doc)
                            p_at_k = hits / len(resp.sources) if resp.sources else 0
                            is_hit = 1 if hits > 0 else 0

                            # Context precision at 1
                            cp_at_1 = (
                                1
                                if retrieved_docs
                                and (target_doc in retrieved_docs[0] or retrieved_docs[0] in target_doc)
                                else 0
                            )

                            # 2. Judges
                            context_block = "\n\n".join([c.content for c in resp.sources])
                            eval_metrics = await self._evaluate_answer(
                                q_item["question"], resp.answer, context_block, q_item["answer"]
                            )

                            pt = resp.usage.prompt_tokens + eval_metrics["judge_prompt_tokens"]
                            ct = resp.usage.completion_tokens + eval_metrics["judge_completion_tokens"]

                            cost = (
                                self._calculate_cost(
                                    resp.usage.prompt_tokens,
                                    resp.usage.completion_tokens,
                                    getattr(self.query_service.llm_client, "model", "llama-3.1-8b-instant"),
                                )
                                + eval_metrics["cost_usd"]
                            )

                            # 3. Telemetry
                            result_entry = {
                                "question": q_item["question"],
                                "ground_truth": q_item["answer"],
                                "generated_answer": resp.answer,
                                "category": q_item["category"],
                                "latency_ms": latency,
                                "precision_at_k": p_at_k,
                                "context_precision_at_1": cp_at_1,
                                "hit": is_hit,
                                "chunking_strategy": c_strat,
                                "retrieval_strategy": r_strat,
                                "strategy_key": strategy_key,
                                "prompt_tokens": pt,
                                "completion_tokens": ct,
                                "cost_usd": cost,
                                "sources": [
                                    {
                                        "content": c.content,
                                        "source": c.metadata.get("source", "unknown"),
                                        "score": float(c.score) if c.score is not None else 0.0,
                                        "chunk_index": c.chunk_index,
                                    }
                                    for c in resp.sources
                                ],
                                **eval_metrics,
                            }
                            overall_results[strategy_key].append(result_entry)
                            print("OK")

                        except Exception as e:
                            print(f"FAILED. Error: {e}")
                            logger.error(f"Error evaluating '{strategy_key}': {e}")

                        current_step += 1
                        self._update_progress(
                            run_dir,
                            {
                                "percentage": (current_step / total_steps) * 100,
                                "current_strategy": strategy_key,
                                "current_chunking": c_strat,
                                "current_retrieval": r_strat,
                                "current_run": run_idx + 1,
                                "last_updated": datetime.now().isoformat(),
                            },
                        )

                    # Write progressive summary (per strategy completion)
                    self._write_summary(run_id, run_dir, overall_results)

                    # Write results.json continuously
                    with open(run_dir / "results.json", "w") as f:
                        json.dump(overall_results, f, indent=2)

        print(
            f"\n[DONE] Evaluation complete! Results saved to {EVAL_RUNS_DIR}/{self.retrieval_strategies[-1]}/{run_id}"
        )


def main():
    parser = argparse.ArgumentParser(description="DeepVault Gold-Standard Evaluation Engine")
    parser.add_argument("--limit", type=int, default=50, help="Number of questions to evaluate per strategy")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the sample set")
    parser.add_argument(
        "--chunking-strategies",
        nargs="+",
        default=["fixed", "sliding", "structure", "semantic"],
        help="Specific chunking strategies to test",
    )
    parser.add_argument(
        "--retrieval-strategies", nargs="+", default=["vector"], help="Specific retrieval strategies to test"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print stats without calling API")

    args = parser.parse_args()

    EVAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    engine = EvalEngine(
        chunking_strategies=args.chunking_strategies,
        retrieval_strategies=args.retrieval_strategies,
        dry_run=args.dry_run,
    )
    asyncio.run(engine.run_benchmark(limit=args.limit, runs=args.runs))


if __name__ == "__main__":
    main()
