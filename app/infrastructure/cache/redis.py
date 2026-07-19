import redis.asyncio as redis

from app.config import settings
from app.infrastructure.logging.structured import logger


class RedisCache:
    """
    Asynchronous Redis wrapper specialized for semantic caching and Background Task queues.
    """

    def __init__(self):
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.client = None

    async def initialize(self) -> None:
        """Initializes the async Redis connection."""
        try:
            self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True)
            # Health check on boot
            from typing import Any, cast

            await cast(Any, self.client.ping())
            logger.info("Connected to Redis successfully.", extra={"extra_fields": {"redis_host": self.host}})
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.client = None
            raise RuntimeError(f"Could not connect to Redis at {self.host}:{self.port}") from e

    async def get(self, key: str) -> str | None:
        """Retrieves a value from Redis returning a decoded string, or None if missing."""
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed for key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: str, ttl_seconds: int = settings.REDIS_TTL_SECONDS) -> None:
        """Stores a string value to Redis with an automated expiration TTL."""
        if not self.client:
            return
        try:
            await self.client.set(key, value, ex=ttl_seconds)
        except Exception as e:
            logger.warning(f"Redis SET failed for key {key}: {str(e)}")

    async def delete(self, key: str) -> None:
        """Deletes a key from Redis."""
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE failed for key {key}: {str(e)}")

    async def incr(self, key: str) -> int:
        """
        Atomically increments the integer value of `key` by 1.
        Returns the new value, or 0 if Redis is unavailable.

        Used by RateLimiter to implement race-free request counting.
        Redis INCR is indivisible — no two callers can race on the same key.
        """
        if not self.client:
            return 0
        try:
            return int(await self.client.incr(key))
        except Exception as e:
            logger.warning(f"Redis INCR failed for key {key}: {str(e)}")
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Sets a TTL on `key`. Returns True if successful, False otherwise.

        Used by RateLimiter to start the fixed-window countdown after the
        first request in a new window.
        """
        if not self.client:
            return False
        try:
            return bool(await self.client.expire(key, seconds))
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed for key {key}: {str(e)}")
            return False

    async def ping(self) -> bool:
        """Direct health ping."""
        if not self.client:
            return False
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Gracefully closes the Redis connection pool."""
        if self.client:
            await self.client.aclose()
            logger.info("Redis connection closed.")
