"""
Fixed-window rate limiter backed by Redis.

Implementation note:
  This uses a simple Redis counter with a TTL as the rate-limiting window.
  It is technically a fixed-window limiter, not a true sliding window.
  A true sliding window (using Redis sorted sets) would prevent bursting
  at window boundaries but adds complexity. The current approach is the
  industry standard for non-critical rate limiting and is sufficient for
  our use case.

Fail-open design:
  If Redis is unavailable, rate limiting is silently bypassed rather
  than rejecting legitimate traffic. This prioritizes availability
  over strict enforcement. For stricter security, change the exception
  handler in rate_limit_dependency() to re-raise instead of logging.

Per-API-key isolation:
  Each API key gets its own Redis counter. This means different callers
  do not share a rate limit — every key gets the full quota independently.
"""

from fastapi.exceptions import HTTPException

from app.infrastructure.cache.redis import RedisCache
from app.infrastructure.logging.structured import logger


class RateLimiter:
    """
    Fixed-window rate limiter.

    Usage:
        limiter = RateLimiter(redis_cache, requests_per_minute=60)
        await limiter.check_rate_limit("my-api-key")

    The limiter stores a Redis counter with a TTL equal to the window size.
    Each call increments the counter; if it exceeds the limit, an HTTP 429
    is raised. The counter naturally expires after the window (TTL = 60s).
    """

    def __init__(self, redis: RedisCache, requests_per_minute: int = 60) -> None:
        self.redis = redis
        self.requests_per_minute = requests_per_minute

    async def check_rate_limit(self, identifier: str) -> None:
        """
        Checks the request count for `identifier` and raises HTTP 429 if exceeded.

        Args:
            identifier: Any string that uniquely identifies the caller.
                        Typically the API key or a hash of the caller's IP.
        """
        key = f"ratelimit:{identifier}"
        window_sec = 60

        redis_val = await self.redis.get(key)
        count = int(redis_val) if redis_val else 0

        if count >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for {identifier[:8]}***",
                extra={"extra_fields": {"identifier": identifier[:8], "count": count}},
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: {self.requests_per_minute} requests per minute. "
                    "Please slow down or contact support for a higher quota."
                ),
            )

        await self.redis.set(key, str(count + 1), ttl_seconds=window_sec)
