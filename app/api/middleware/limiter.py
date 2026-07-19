"""
Fixed-window rate limiter backed by Redis.

Implementation note:
  This uses Redis INCR (atomic increment) + EXPIRE to implement a fixed-window
  counter. INCR is a single, indivisible server-side operation — no two clients
  can race on the same counter, unlike the previous GET→conditional-SET pattern
  which was vulnerable to a TOCTOU race (two workers could both read count=N,
  both pass the check, and both write N+1).

  Redis guarantees:
    1. INCR returns the new value atomically.
    2. We set EXPIRE only on the first request in a window (when count == 1)
       so the TTL is not reset on every hit.

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
    Fixed-window rate limiter using atomic Redis INCR.

    Usage:
        limiter = RateLimiter(redis_cache, requests_per_minute=60)
        await limiter.check_rate_limit("my-api-key")

    How it works:
        1. INCR the key — returns the new count atomically (race-free).
        2. If count == 1 (first request in window), set EXPIRE = window_sec.
           We only set TTL once so the window doesn't slide on each hit.
        3. If count > limit, raise 429.
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

        # Atomic increment — a single Redis round-trip, no race condition possible
        count = await self.redis.incr(key)

        # Set TTL only on the first request of each window.
        # Subsequent requests must NOT reset the TTL — that would allow a
        # client to keep the window open indefinitely by hitting the API
        # continuously, effectively bypassing the rate limit.
        if count == 1:
            await self.redis.expire(key, window_sec)

        if count > self.requests_per_minute:
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
