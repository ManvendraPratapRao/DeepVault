import argparse
import asyncio
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
import os
sys.path.append(os.getcwd())

import numpy as np
from app.config import settings
from app.core.models.query import QueryRequest
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.logging.structured import logger
from app.services.query import QueryService
from app.dependencies import get_query_service, initialize_all
from app.prompts.v1 import JUDGE_FAITHFULNESS_PROMPT, JUDGE_RELEVANCE_PROMPT

# Configuration
RESULTS_FILE = Path("data/metrics_smoke_test_results.json")
PROGRESS_FILE = Path("data/eval_progress.json")
JUDGE_MODEL = "llama-3.1-70b-versatile"

class EvalEngine:
    """
    Gold-Standard Evaluation Engine.
    Orchestrates comparative benchmarking across retrieval strategies.
    """
    def __init__(self, strategies=None, judge_model=JUDGE_MODEL):
        self.query_service = None # Latent init
        self.judge_client = GroqLLMClient()
        self.judge_client.model = judge_model
        self.embedder = BgeEmbedder()
        self.strategies = strategies or ["fixed", "sliding", "structure", "semantic"]
        
    async def initialize(self):
        """Prepares infrastructure and services."""
        await initialize_all()
        self.query_service = await get_query_service()

    def _load_questions(self) -> List[Dict[str, Any]]:
        """Loads golden QA datasets from research and synthetic directories."""
        research_file = Path("data/research_papers_golden_qa.json")
        synthetic_file = Path("synthetic_data_v2/golden_qa_dataset.json")
        
        all_q = []
        if research_file.exists():
            with open(research_file, "r") as f:
                data = json.load(f)
                for item in data:
                    all_q.append({**item, "category": "research"})
                    
        if synthetic_file.exists():
            with open(synthetic_file, "r") as f:
                data = json.load(f)
                for item in data:
                    all_q.append({**item, "category": "synthetic"})
        
        return all_q

    def _get_balanced_sample(self, questions: List[Dict[str, Any]], total_limit: int = 250) -> List[Dict[str, Any]]:
        """Splits the sample between research and synthetic domains."""
        research_q = [q for q in questions if q["category"] == "research"]
        synthetic_q = [q for q in questions if q["category"] == "synthetic"]
        
        # Determine splits (60% research, 40% synthetic)
        r_limit = int(total_limit * 0.6)
        s_limit = total_limit - r_limit

        sample = random.sample(research_q, min(r_limit, len(research_q)))
        sample.extend(random.sample(synthetic_q, min(s_limit, len(synthetic_q))))
        random.shuffle(sample)
        return sample

    def _parse_judge_json(self, raw_response: str) -> Dict[str, Any]:
        """Robustly extracts and parses JSON from LLM responses."""
        try:
            # Clean possible markdown formatting
            clean_str = re.sub(r"```json\s*|\s*```", "", raw_response).strip()
            return json.loads(clean_str)
        except Exception:
            # Fallback for non-JSON or partial responses
            logger.warning(f"Judge returned non-JSON response: {raw_response[:100]}...")
            return {"score": 3, "reasoning": "Failed to parse judge response."}

    def _cosine_similarity(self, vec1, vec2):
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    async def _evaluate_answer(self, question: str, answer: str, context: str, ground_truth: str):
        """Runs the twin-judge and deterministic similarity evaluation."""
        # 1. Faithfulness (Judge)
        faith_prompt = JUDGE_FAITHFULNESS_PROMPT.format(context=context, answer=answer)
        faith_res = await self.judge_client.generate(faith_prompt)
        faith_eval = self._parse_judge_json(faith_res.answer)

        # 2. Relevance (Judge)
        rel_prompt = JUDGE_RELEVANCE_PROMPT.format(question=question, answer=answer)
        rel_res = await self.judge_client.generate(rel_prompt)
        rel_eval = self._parse_judge_json(rel_res.answer)

        # 3. Semantic Similarity (BGE)
        v1 = await self.embedder.embed_text(answer) # Fix: use embed_text
        v2 = await self.embedder.embed_text(ground_truth)
        sim = float(self._cosine_similarity(v1, v2))

        return {
            "faithfulness": faith_eval["score"],
            "faithfulness_reasoning": faith_eval.get("reasoning", ""),
            "relevance": rel_eval["score"],
            "relevance_reasoning": rel_eval.get("reasoning", ""),
            "similarity": sim,
            "hallucination": 1 if faith_eval["score"] <= 2 else 0
        }

    async def run_benchmark(self, limit: int = 250, runs: int = 1):
        """
        Executes the full evaluation pipeline.
        Captures deep telemetry for dashboard diagnostics.
        """
        await self.initialize()
        questions = self._load_questions()
        if not questions:
            logger.error("No questions found in dataset!")
            return

        overall_results = {s: [] for s in self.strategies}
        total_steps = len(self.strategies) * runs * limit
        current_step = 0

        for run_idx in range(runs):
            sample = self._get_balanced_sample(questions, total_limit=limit)
            
            for strategy in self.strategies:
                logger.info(f"🚀 Starting Strategy Pass: {strategy} (Run {run_idx+1}/{runs})")
                
                for q_idx, q_item in enumerate(sample):
                    try:
                        start_time = time.perf_counter()
                        req = QueryRequest(query_text=q_item["question"], strategy=strategy, top_k=5)
                        resp = await self.query_service.ask(req)
                        latency = (time.perf_counter() - start_time) * 1000
                        
                        # 1. Retrieval Analysis (P@k and R@k)
                        retrieved_docs = [c.metadata.get("source", "").lower() for c in resp.sources]
                        target_doc = q_item["source_document"].lower()
                        
                        # Logic: Hit is a match in ANY source. Precision is hits / k.
                        hits = sum(1 for d in retrieved_docs if target_doc in d or d in target_doc)
                        p_at_k = hits / len(resp.sources) if resp.sources else 0
                        is_hit = 1 if hits > 0 else 0
                        
                        # 2. Pack context and Run Judges
                        context_block = "\n\n".join([c.content for c in resp.sources])
                        eval_metrics = await self._evaluate_answer(
                            q_item["question"], resp.answer, context_block, q_item["answer"]
                        )
                        
                        # 3. Deep Data Capture for Dashboard X-Ray
                        result_entry = {
                            "question": q_item["question"],
                            "ground_truth": q_item["answer"],
                            "generated_answer": resp.answer,
                            "category": q_item["category"],
                            "latency_ms": latency,
                            "precision_at_k": p_at_k,
                            "hit": is_hit,
                            "usage": resp.usage.model_dump(),
                            "sources": [
                                {
                                    "content": c.content,
                                    "source": c.metadata.get("source", "unknown"),
                                    "score": c.score,
                                    "chunk_index": c.chunk_index
                                } for c in resp.sources
                            ],
                            **eval_metrics
                        }
                        overall_results[strategy].append(result_entry)
                        
                    except Exception as e:
                        logger.error(f"Error evaluating query '{q_item['question'][:30]}': {e}")
                    
                    current_step += 1
                    # Update Progress for Dashboard UI
                    with open(PROGRESS_FILE, "w") as f:
                        json.dump({
                            "percentage": (current_step / total_steps) * 100,
                            "current_strategy": strategy,
                            "current_run": run_idx + 1,
                            "last_updated": datetime.now().isoformat()
                        }, f)

        # 4. Persistence
        final_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "runs": runs,
                "limit_per_run": limit,
                "judge_model": self.judge_client.model,
                "strategies": self.strategies
            },
            "results": overall_results
        }
        
        with open(RESULTS_FILE, "w") as f:
            json.dump(final_data, f, indent=2)
        
        logger.info(f"✅ Evaluation Complete! Results saved to {RESULTS_FILE}")

def main():
    parser = argparse.ArgumentParser(description="DeepVault Gold-Standard Evaluation Engine")
    parser.add_argument("--limit", type=int, default=10, help="Number of questions to evaluate per strategy")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the sample set")
    parser.add_argument("--strategies", nargs="+", help="Specific strategies to test (default: all)")
    
    args = parser.parse_args()
    
    engine = EvalEngine(strategies=args.strategies)
    asyncio.run(engine.run_benchmark(limit=args.limit, runs=args.runs))

if __name__ == "__main__":
    main()
