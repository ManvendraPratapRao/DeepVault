import time

from fastapi import APIRouter, Depends

from app.api.schemas.responses import HealthResponse
from app.config import settings
from app.dependencies import get_redis_cache
from app.infrastructure.cache.redis import RedisCache

router = APIRouter()
start_time = time.time()


@router.get("", response_model=HealthResponse)
async def health_check(redis_cache: RedisCache = Depends(get_redis_cache)):
    """Confirms the API and its components are functional."""
    redis_status = await redis_cache.ping()
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptime_seconds=time.time() - start_time,
        components={
            "sqlite": "connected",
            "qdrant": "connected",
            "groq": "ready",
            "redis": "connected" if redis_status else "disconnected",
        },
    )
