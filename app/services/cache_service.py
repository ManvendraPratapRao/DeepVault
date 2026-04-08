import hashlib
import json

from app.config import settings
from app.core.models.query import QueryResponse
from app.infrastructure.cache.redis import RedisCache
from app.infrastructure.logging.structured import logger


class CacheService:
    """
    Business logic wrapper around Redis.
    Responsible for generating key shapes and securely deserializing structures like QueryResponse.
    """

    def __init__(self, redis_cache: RedisCache):
        self.redis = redis_cache

    async def get_cached_response(self, query_text: str) -> QueryResponse | None:
        """Looks up a generated QueryResponse by hashing the exact query string."""
        if not settings.CACHE_ENABLED:
            return None

        key = f"query:{hashlib.md5(query_text.encode()).hexdigest()}"
        raw_val = await self.redis.get(key)

        if raw_val:
            try:
                data = json.loads(raw_val)
                logger.info(f"Query Cache HIT for key: {key}", extra={"extra_fields": {"cache_hit": True, "key": key}})
                return QueryResponse(**data)
            except Exception as e:
                logger.warning(f"Failed to deserialize cache payload for {key}: {str(e)}")

        return None

    async def cache_response(self, query_text: str, response: QueryResponse) -> None:
        """Serializes and saves a QueryResponse."""
        if not settings.CACHE_ENABLED:
            return

        key = f"query:{hashlib.md5(query_text.encode()).hexdigest()}"
        try:
            # Pydantic v2: model_dump_json() returns a string
            payload = response.model_dump_json()
            await self.redis.set(key, payload, ttl_seconds=settings.REDIS_TTL_SECONDS)
            logger.info(
                f"Query Cache SET for key: {key}",
                extra={"extra_fields": {"cache_set": True, "key": key, "ttl": settings.REDIS_TTL_SECONDS}},
            )
        except Exception as e:
            logger.warning(f"Failed to cache response for {key}: {str(e)}")

    async def get_cached_embedding(self, text: str) -> list[float] | None:
        """Looks up a cached vector representation of a sentence/chunk."""
        if not settings.EMBEDDING_CACHE_ENABLED:
            return None

        key = f"embed:{hashlib.sha256(text.encode()).hexdigest()}"
        raw_val = await self.redis.get(key)

        if raw_val:
            try:
                return json.loads(raw_val)
            except Exception as e:
                logger.warning(f"Failed to deserialize embedding cache for {key}: {str(e)}")

        return None

    async def cache_embedding(self, text: str, embedding: list[float]) -> None:
        """Serializes and saves an embedding array."""
        if not settings.EMBEDDING_CACHE_ENABLED:
            return

        key = f"embed:{hashlib.sha256(text.encode()).hexdigest()}"
        try:
            payload = json.dumps(embedding)
            # Embeddings usually don't expire quickly,
            # maybe use a 30-day generic TTL, but using generic default for now
            await self.redis.set(key, payload, ttl_seconds=settings.REDIS_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Failed to cache embedding for {key}: {str(e)}")
