"""
Prometheus metrics instrumentation for DeepVault.

All metric objects are module-level singletons — Prometheus requires this.
Services import the helper functions (record_query, record_cache_op, etc.)
rather than the metric objects directly, keeping coupling low.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------------------------
# HTTP-level metrics (populated by MetricsMiddleware)
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "deepvault_http_requests_total",
    "Total HTTP requests processed",
    labelnames=["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "deepvault_http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "path"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# ---------------------------------------------------------------------------
# RAG query metrics (populated by QueryService)
# ---------------------------------------------------------------------------

QUERY_TOTAL = Counter(
    "deepvault_query_total",
    "Total RAG queries processed",
    labelnames=["retrieval_strategy", "chunking_strategy", "status"],
)

QUERY_DURATION = Histogram(
    "deepvault_query_duration_seconds",
    "End-to-end RAG query latency in seconds",
    labelnames=["retrieval_strategy", "chunking_strategy"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0],
)

# ---------------------------------------------------------------------------
# LLM cost and token metrics (populated by QueryService)
# ---------------------------------------------------------------------------

LLM_TOKENS_TOTAL = Counter(
    "deepvault_llm_tokens_total",
    "Total LLM tokens consumed",
    labelnames=["token_type"],  # "prompt" | "completion"
)

LLM_COST_USD_TOTAL = Counter(
    "deepvault_llm_cost_usd_total",
    "Estimated total LLM cost in USD (Groq Llama-3.3-70b pricing)",
)

# ---------------------------------------------------------------------------
# Cache metrics (populated by CacheService)
# ---------------------------------------------------------------------------

CACHE_OPS_TOTAL = Counter(
    "deepvault_cache_operations_total",
    "Cache lookup results",
    labelnames=["cache_type", "result"],  # cache_type=query|embedding, result=hit|miss
)

# ---------------------------------------------------------------------------
# Ingestion metrics (populated by IngestionService)
# ---------------------------------------------------------------------------

INGESTION_TOTAL = Counter(
    "deepvault_ingestion_total",
    "Total document ingestion attempts",
    labelnames=["chunking_strategy", "status"],  # status=success|duplicate|error
)

INGESTION_CHUNKS_TOTAL = Histogram(
    "deepvault_ingestion_chunks_per_document",
    "Number of chunks produced per ingested document",
    labelnames=["chunking_strategy"],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500],
)


# ---------------------------------------------------------------------------
# Helper functions — the only public API for services to call
# ---------------------------------------------------------------------------

# Groq Llama-3.3-70b pricing (as of 2025): $0.59 / 1M input tokens, $0.79 / 1M output tokens
_PROMPT_COST_PER_TOKEN = 0.59 / 1_000_000
_COMPLETION_COST_PER_TOKEN = 0.79 / 1_000_000


def record_query_metrics(
    retrieval_strategy: str,
    chunking_strategy: str,
    duration_seconds: float,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Called by QueryService after each query (success or failure)."""
    strat = retrieval_strategy or "vector"
    chunk = chunking_strategy or "fixed"

    QUERY_TOTAL.labels(retrieval_strategy=strat, chunking_strategy=chunk, status=status).inc()
    QUERY_DURATION.labels(retrieval_strategy=strat, chunking_strategy=chunk).observe(duration_seconds)

    if prompt_tokens:
        LLM_TOKENS_TOTAL.labels(token_type="prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS_TOTAL.labels(token_type="completion").inc(completion_tokens)

    cost = (prompt_tokens * _PROMPT_COST_PER_TOKEN) + (completion_tokens * _COMPLETION_COST_PER_TOKEN)
    if cost > 0:
        LLM_COST_USD_TOTAL.inc(cost)


def record_cache_op(cache_type: str, hit: bool) -> None:
    """Called by CacheService on every get operation."""
    result = "hit" if hit else "miss"
    CACHE_OPS_TOTAL.labels(cache_type=cache_type, result=result).inc()


def record_ingestion(chunking_strategy: str, status: str, chunks_created: int = 0) -> None:
    """Called by IngestionService after each ingest_text() call."""
    strat = chunking_strategy or "unknown"
    INGESTION_TOTAL.labels(chunking_strategy=strat, status=status).inc()
    if chunks_created > 0:
        INGESTION_CHUNKS_TOTAL.labels(chunking_strategy=strat).observe(chunks_created)


def get_metrics_output() -> tuple[bytes, str]:
    """Returns (content_bytes, content_type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
