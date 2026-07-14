"""
eval/config.py
==============
Strategy matrices and shared constants for all DeepVault eval runs.
Now features Multi-Model Load Balancing to bypass token limits.
"""
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_RUNS_DIR = PROJECT_ROOT / "data" / "eval_runs"
SYNTHETIC_QA_PATH = PROJECT_ROOT / "synthetic_data_v2" / "golden_qa_dataset.json"

# ---------------------------------------------------------------------------
# Strategy matrices
# ---------------------------------------------------------------------------

# V1: Base strategies 
V1_CHUNKING_STRATEGIES = ["sliding", "recursive", "structure", "semantic"]
V1_RETRIEVAL_STRATEGIES = ["vector", "hybrid", "hybrid_rerank"]

# V2: Rewrite variants 
V2_RETRIEVAL_STRATEGIES = ["vector_rewrite", "hybrid_rewrite", "hybrid_rerank_rewrite"]

# All base retrieval strategies (V1 + V2, no duplication)
ALL_RETRIEVAL_STRATEGIES = V1_RETRIEVAL_STRATEGIES + V2_RETRIEVAL_STRATEGIES

# ---------------------------------------------------------------------------
# Model constants & Rotator
# ---------------------------------------------------------------------------
# We use LiteLLM format: 'groq/<model_name>' for Groq models
GENERATOR_POOL = [
    "groq/llama-3.1-8b-instant",
    "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/openai/gpt-oss-20b",
    "groq/qwen/qwen3-32b", 
    "groq/qwen/qwen3.6-27b"
]

JUDGE_POOL = [
    "groq/llama-3.1-8b-instant",
    "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/openai/gpt-oss-20b",
    "groq/qwen/qwen3-32b",
    "groq/qwen/qwen3.6-27b"
]

JUDGE_MODEL_70B = "groq/llama-3.3-70b-versatile"

# Standard Pricing mapping (used to calculate operational cost)
# If using open-source on Groq, we assume $0.05/M input and $0.08/M output as a baseline for the free tier.
GROQ_PRICING = {
    "default": {"input": 0.05, "output": 0.08},
    "groq/llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}

class ModelRotator:
    """Round-robin model rotator to bypass token limits."""
    def __init__(self, models: list[str]):
        self.models = models
        self.index = 0
        
    def get_next(self) -> str:
        model = self.models[self.index]
        self.index = (self.index + 1) % len(self.models)
        return model

# ---------------------------------------------------------------------------
# Eval settings
# ---------------------------------------------------------------------------
DEFAULT_TOP_K: int = 10
DEFAULT_LIMIT: int = 100      
RANDOM_SEED: int = 42

# 0.1 for high determinism but slight flexibility in edge cases
EVAL_TEMPERATURE: float = 0.1 

# Rate limiter — limits to 12 RPM to prevent blowing up the TPM
DEFAULT_RPM: int = 12


@dataclass
class EvalRunConfig:
    """
    Captures the full configuration of a single evaluation run.
    """
    run_id: str
    chunking_strategies: list[str] = field(default_factory=lambda: V1_CHUNKING_STRATEGIES)
    retrieval_strategies: list[str] = field(default_factory=lambda: V1_RETRIEVAL_STRATEGIES)
    limit: int = DEFAULT_LIMIT
    top_k: int = DEFAULT_TOP_K
    rpm: int = DEFAULT_RPM
    dry_run: bool = False
    phase: str = "v1"
    generator: str | None = None
    judge: str | None = None

    def combinations(self) -> list[tuple[str, str]]:
        """Returns all (chunking, retrieval) pairs for this run."""
        return [
            (c, r)
            for c in self.chunking_strategies
            for r in self.retrieval_strategies
        ]

    def strategy_key(self, chunking: str, retrieval: str) -> str:
        return f"{chunking}__{retrieval}"
