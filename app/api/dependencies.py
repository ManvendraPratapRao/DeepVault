from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.api.middleware.limiter import RateLimiter
from app.config import settings
from app.dependencies import get_redis_cache
from app.infrastructure.cache.redis import RedisCache

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)):
    """Validates the X-API-KEY header against the configured secret."""
    if api_key == settings.API_KEY:
        return api_key
    raise HTTPException(status_code=403, detail="Could not validate credentials")


async def rate_limit_dependency(
    request: Request, api_key: str = Depends(get_api_key), redis: RedisCache = Depends(get_redis_cache)
):
    """
    Enforces a rate limit of 60 requests per minute per API Key.
    Fails open if Redis is unavailable to prioritize availability.
    """
    try:
        limiter = RateLimiter(redis, requests_per_minute=60)
        await limiter.check_rate_limit(api_key)
    except Exception as e:
        from app.infrastructure.logging.structured import logger

        logger.warning(f"Rate limiter failed (Redis issue?), failing open: {str(e)}")

    return api_key
