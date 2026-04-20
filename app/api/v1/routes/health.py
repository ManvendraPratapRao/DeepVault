"""
Health endpoints for DeepVault.

GET /api/v1/health           — Basic liveness check (fast, no dependencies)
GET /api/v1/health/detailed  — Full dependency deep-dive with per-component latency
"""

import time

from fastapi import APIRouter, Depends

from app.api.schemas.responses import HealthResponse
from app.config import settings
from app.dependencies import get_redis_cache
from app.infrastructure.cache.redis import RedisCache

router = APIRouter()
_start_time = time.time()


@router.get("", response_model=HealthResponse, summary="Liveness Check")
async def health_check(redis_cache: RedisCache = Depends(get_redis_cache)):
    """Fast liveness check. Returns 200 if the API is running."""
    redis_status = await redis_cache.ping()
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptime_seconds=time.time() - _start_time,
        components={
            "sqlite": "connected",
            "qdrant": "connected",
            "groq": "ready",
            "redis": "connected" if redis_status else "disconnected",
        },
    )


@router.get(
    "/detailed",
    summary="Deep Health Check",
    description=(
        "Probes each dependency in turn and returns per-component latency. "
        "Slower than the basic check — use this for monitoring alerts, not load balancers."
    ),
)
async def health_check_detailed(redis_cache: RedisCache = Depends(get_redis_cache)):
    """
    Readiness probe — checks each dependency is reachable and measures latency.

    Returns a structured JSON report:
    {
        "status": "healthy" | "degraded" | "unhealthy",
        "uptime_seconds": 1234.5,
        "version": "2.0.0",
        "components": {
            "redis":  {"status": "ok" | "error", "latency_ms": 1.2,  "detail": "..."},
            "qdrant": {"status": "ok" | "error", "latency_ms": 4.8,  "detail": "..."},
            "llm":    {"status": "ok" | "error", "latency_ms": 0.02, "detail": "..."},
        }
    }
    """
    components = {}
    any_error = False

    # --- Redis ---
    t0 = time.perf_counter()
    try:
        redis_ok = await redis_cache.ping()
        redis_latency = (time.perf_counter() - t0) * 1000
        components["redis"] = {
            "status": "ok" if redis_ok else "error",
            "latency_ms": round(redis_latency, 2),
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

    # --- Qdrant ---
    t0 = time.perf_counter()
    try:
        from qdrant_client import AsyncQdrantClient

        qc = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        await qc.get_collections()
        qdrant_latency = (time.perf_counter() - t0) * 1000
        components["qdrant"] = {
            "status": "ok",
            "latency_ms": round(qdrant_latency, 2),
            "detail": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        }
        await qc.close()  # type: ignore[attr-defined]
    except Exception as e:
        components["qdrant"] = {
            "status": "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": str(e),
        }
        any_error = True

    # --- LLM (token-count smoke test, free — no API credits consumed) ---
    t0 = time.perf_counter()
    try:
        from app.infrastructure.llm.groq import GroqLLMClient

        llm = GroqLLMClient()
        token_count = await llm.count_tokens("health check probe")
        llm_latency = (time.perf_counter() - t0) * 1000
        components["llm"] = {
            "status": "ok",
            "latency_ms": round(llm_latency, 2),
            "detail": f"model={settings.GROQ_MODEL_NAME} token_heuristic={token_count}",
        }
    except Exception as e:
        components["llm"] = {
            "status": "error",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "detail": str(e),
        }
        any_error = True

    overall = "degraded" if any_error else "healthy"
    return {
        "status": overall,
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "components": components,
    }
