import time
from fastapi import Request, HTTPException
from app.infrastructure.cache.redis import RedisCache
from app.infrastructure.logging.structured import logger

class RateLimiter:
    """
    A simple sliding window rate limiter backed by Redis.
    """
    def __init__(self, redis: RedisCache, requests_per_minute: int = 60):
        self.redis = redis
        self.requests_per_minute = requests_per_minute

    async def check_rate_limit(self, identifier: str):
        """
        Increments the request count for a given identifier (e.g., API Key or IP).
        Raises HTTPException 429 if the limit is exceeded.
        """
        now = int(time.time())
        window_sec = 60
        key = f"rl:{identifier}:{now // window_sec}"
        
        # Increment the count for the current minute
        # We use a simple window approach for performance
        count = await self.redis.get(key)
        count = int(count) if count else 0
        
        if count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {identifier}")
            raise HTTPException(
                status_code=429, 
                detail="Too many requests. Please slow down."
            )
            
        await self.redis.set(key, str(count + 1), ttl_seconds=window_sec)

# Helper function to be used as a FastAPI dependency
async def rate_limit(request: Request, redis: RedisCache = None):
    # This will be refined as we integrate it into the routes
    pass
