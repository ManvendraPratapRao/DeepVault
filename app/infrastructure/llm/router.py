"""
LLM Router — selects the optimal model based on query complexity and cost constraints.

Phase 5 / Session 25 feature.

Strategy:
    Simple queries (factual, short)  → llama-3.1-8b-instant   (fast, cheap)
    Complex queries (semantic, long) → llama-3.3-70b-versatile (high quality)

Cost tiers (Groq, approximate per 1M tokens):
    llama-3.1-8b-instant     ~ $0.05 input / $0.08 output
    llama-3.3-70b-versatile  ~ $0.59 input / $0.79 output

The router estimates query complexity from:
    1. Query type (from QueryClassifier)
    2. Word count (proxy for context size)
    3. Context length (retrieved chunks)

This allows the system to save ~90% on token costs for simple queries
while still using the powerful model when quality matters.
"""

from dataclasses import dataclass

from app.infrastructure.logging.structured import logger

# ---------------------------------------------------------------------------
# Model tiers
# ---------------------------------------------------------------------------

FAST_MODEL = "llama-3.1-8b-instant"  # Cheap + fast for simple queries
QUALITY_MODEL = "llama-3.3-70b-versatile"  # Best quality for complex queries

# Groq pricing (USD per 1M tokens, approximate as of 2026)
_COST_PER_M = {
    FAST_MODEL: {"input": 0.05, "output": 0.08},
    QUALITY_MODEL: {"input": 0.59, "output": 0.79},
}

# Query complexity thresholds
_COMPLEX_QUERY_TYPES = {"comparison", "complex"}
_LONG_QUERY_WORDS = 15  # Queries above this word count are routed to quality model
_LARGE_CONTEXT_CHARS = 4000  # Context above this size benefits from stronger reasoning


@dataclass
class ModelSelection:
    model_name: str
    reason: str
    estimated_cost_per_1k_tokens: float


class LLMRouter:
    """
    Routes LLM generation requests to the appropriate model tier based on
    query complexity, context size, and quality requirements.

    Usage:
        router = LLMRouter()
        selection = router.select(query_type="complex", query_text=q, context=ctx)
        # selection.model_name → "llama-3.3-70b-versatile"
    """

    def select(
        self,
        query_type: str | None = None,
        query_text: str = "",
        context: str = "",
        force_quality: bool = False,
    ) -> ModelSelection:
        """
        Selects the appropriate model for a given query.

        Args:
            query_type:    Classification from QueryClassifier ('factual', 'semantic', etc.)
            query_text:    The raw user query.
            context:       Retrieved context string (used to estimate reasoning load).
            force_quality: If True, always use the quality model regardless of query type.

        Returns:
            ModelSelection with model name and routing rationale.
        """
        if force_quality:
            return ModelSelection(
                model_name=QUALITY_MODEL,
                reason="force_quality=True",
                estimated_cost_per_1k_tokens=(
                    _COST_PER_M[QUALITY_MODEL]["input"] + _COST_PER_M[QUALITY_MODEL]["output"]
                )
                / 2000,
            )

        word_count = len(query_text.split())
        context_len = len(context)

        # Route to quality model if any complexity signal is present
        use_quality = (
            query_type in _COMPLEX_QUERY_TYPES or word_count >= _LONG_QUERY_WORDS or context_len >= _LARGE_CONTEXT_CHARS
        )

        model = QUALITY_MODEL if use_quality else FAST_MODEL
        cost = (_COST_PER_M[model]["input"] + _COST_PER_M[model]["output"]) / 2000

        reasons = []
        if query_type in _COMPLEX_QUERY_TYPES:
            reasons.append(f"query_type={query_type!r}")
        if word_count >= _LONG_QUERY_WORDS:
            reasons.append(f"word_count={word_count}")
        if context_len >= _LARGE_CONTEXT_CHARS:
            reasons.append(f"context_len={context_len}")
        if not reasons:
            reasons.append("simple_factual")

        reason = " + ".join(reasons)

        logger.info(
            f"LLMRouter: {model} ({reason})",
            extra={"extra_fields": {"model": model, "reason": reason, "query_type": query_type}},
        )

        return ModelSelection(model_name=model, reason=reason, estimated_cost_per_1k_tokens=cost)

    @staticmethod
    def estimate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimates the USD cost for a given model and token counts.

        Args:
            model_name:        The Groq model name.
            prompt_tokens:     Number of input tokens.
            completion_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        pricing = _COST_PER_M.get(model_name, _COST_PER_M[QUALITY_MODEL])
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
