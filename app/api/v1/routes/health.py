"""
Health check endpoints for DeepVault.

GET /api/v1/health          — Basic liveness check (fast, no dependency probing)
GET /api/v1/health/detailed — Full readiness check with per-component latency

Design intent:
  - Liveness (/health) is called by load balancers every few seconds.
    It must be fast and must not make external calls.
  - Readiness (/health/detailed) is for monitoring dashboards and alerts.
    It probes each dependency and reports individual latency and status.

The two-endpoint pattern follows the Kubernetes liveness/readiness probe
convention even though we are not running in K8s right now. This makes
future migration straightforward.
"""

import time

from fastapi import APIRouter, Depends
from qdrant_client import AsyncQdrantClient

from app.api.schemas.responses import HealthResponse
from app.config import settings
from app.dependencies import get_qdrant_client, get_redis_cache
from app.infrastructure.cache.redis import RedisCache

router = APIRouter()
_start_time = time.time()


@router.get("", response_model=HealthResponse, summary="Liveness Check")
async def health_check(redis_cache: RedisCache = Depends(get_redis_cache)) -> HealthResponse:
    """
    Fast liveness check.

    Returns 200 if the API process is running. Probes Redis briefly
    to confirm the caching layer is reachable but does NOT probe Qdrant
    or the LLM (those are reserved for /detailed).
    """
    redis_status = await redis_cache.ping()
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptime_seconds=time.time() - _start_time,
        components={
            "redis": "connected" if redis_status else "disconnected",
            # SQLite and Qdrant are NOT probed in the liveness check —
            # use /health/detailed for full readiness verification.
        },
    )


@router.get(
    "/detailed",
    summary="Deep Readiness Check",
    description=(
        "Probes each dependency in turn and returns per-component latency. "
        "Slower than the basic check — use this for monitoring alerts, not load balancers."
    ),
)
async def health_check_detailed(
    redis_cache: RedisCache = Depends(get_redis_cache),
    qdrant_client: AsyncQdrantClient = Depends(get_qdrant_client),
) -> dict:
    """
    Readiness probe — checks each dependency is reachable and measures latency.

    Returns a structured JSON report with overall status and per-component
    details. Status is "healthy" only if ALL dependencies are reachable.
    Status is "degraded" if any dependency fails.

    Example response:
        {
            "status": "healthy",
            "version": "4.0.0",
            "uptime_seconds": 1234.5,
            "components": {
                "redis":  {"status": "ok", "latency_ms": 0.8,  "detail": "pong"},
                "qdrant": {"status": "ok", "latency_ms": 2.1,  "detail": "localhost:6333"},
                "llm":    {"status": "ok", "latency_ms": 0.02, "detail": "model=llama-3.1-8b-instant token_heuristic=4"}
            }
        }
    """
    components: dict = {}
    any_error = False

    # --- Redis ---
    t0 = time.perf_counter()
    try:
        redis_ok = await redis_cache.ping()
        components["redis"] = {
            "status": "ok" if redis_ok else "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": "pong" if redis_ok else "ping returned False",
        }
        if not redis_ok:
            any_error = True
    except Exception as e:
        components["redis"] = {
            "status": "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": str(e),
        }
        any_error = True

    # --- Qdrant (reuses the shared singleton — no new connection overhead) ---
    t0 = time.perf_counter()
    try:
        await qdrant_client.get_collections()
        components["qdrant"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        }
    except Exception as e:
        components["qdrant"] = {
            "status": "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": str(e),
        }
        any_error = True

    # --- LLM (token-count smoke test — free, no API credits consumed) ---
    t0 = time.perf_counter()
    try:
        from app.infrastructure.llm.groq import GroqLLMClient

        llm = GroqLLMClient()
        token_count = await llm.count_tokens("health check probe")
        components["llm"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": f"model={settings.GROQ_MODEL_NAME} token_heuristic={token_count}",
        }
    except Exception as e:
        components["llm"] = {
            "status": "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": str(e),
        }
        any_error = True

    return {
        "status": "degraded" if any_error else "healthy",
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "components": components,
    }
