import json
from unittest.mock import AsyncMock

import pytest

from app.core.models.query import QueryResponse
from app.infrastructure.cache.redis import RedisCache
from app.services.cache_service import CacheService


@pytest.fixture
def mock_redis():
    mock = AsyncMock(spec=RedisCache)
    return mock


@pytest.fixture
def cache_service(mock_redis):
    # Tests usually manipulate configs using pytest monkeypatch, but here
    # we just run the default settings where CACHE_ENABLED is True.
    return CacheService(redis_cache=mock_redis)


@pytest.mark.asyncio
async def test_get_cached_response_miss(cache_service, mock_redis):
    # Simulate Redis returning nothing
    mock_redis.get.return_value = None

    result = await cache_service.get_cached_response("What is DeepVault?")
    assert result is None
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_cached_response_hit(cache_service, mock_redis):
    # Simulate a successful Redis cache retrieval
    dummy_query_response = QueryResponse(
        answer="It is a RAG system.", sources=[], latency_ms=10.5, request_id="test_id"
    )

    mock_redis.get.return_value = dummy_query_response.model_dump_json()

    result = await cache_service.get_cached_response("What is DeepVault?")
    assert result is not None
    assert result.answer == "It is a RAG system."
    assert result.latency_ms == 10.5


@pytest.mark.asyncio
async def test_cache_response(cache_service, mock_redis):
    dummy_query_response = QueryResponse(answer="Hello World", sources=[], latency_ms=50.0, request_id="test_set_id")

    await cache_service.cache_response("Test cache query", dummy_query_response)
    mock_redis.set.assert_called_once()

    # Verify the payload passed to Redis was stringified properly
    args, kwargs = mock_redis.set.call_args
    assert isinstance(args[1], str)
    assert "Hello World" in args[1]


@pytest.mark.asyncio
async def test_get_cached_embedding(cache_service, mock_redis):
    dummy_emb = [0.1, 0.2, 0.3]
    mock_redis.get.return_value = json.dumps(dummy_emb)

    result = await cache_service.get_cached_embedding("Make vector")
    assert result == dummy_emb
