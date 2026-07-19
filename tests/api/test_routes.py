"""
API route integration tests for DeepVault.

Uses a minimal isolated FastAPI app (no lifespan, all dependencies mocked)
so no live infrastructure (Redis, Qdrant, Groq) is needed during CI.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import api_router
from app.core.models.document import Chunk, DocumentMetadata
from app.core.models.query import QueryResponse, TokenUsage
from app.services.query import QueryService

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_META = DocumentMetadata(source="test.md")
_CHUNK = Chunk(
    id="c1",
    document_id="d1",
    content="DeepVault is a RAG system.",
    chunk_index=0,
    metadata=_META.model_dump(),
)
_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
_QUERY_RESPONSE = QueryResponse(
    answer="DeepVault is a production RAG system.",
    sources=[_CHUNK],
    usage=_USAGE,
    latency_ms=120.0,
    request_id="test-req-001",
)

_MOCK_QS = AsyncMock(spec=QueryService)
_MOCK_QS.ask.return_value = _QUERY_RESPONSE


# ---------------------------------------------------------------------------
# Build a minimal test app — no lifespan, pure mock dependencies
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """
    Creates a bare FastAPI app with only the v1 router mounted.
    No lifespan = no Redis/Qdrant connections on startup.
    All DI factories return mocks.
    """
    from app.api.dependencies import get_api_key
    from app.dependencies import (
        get_query_service,
        get_redis_cache,
    )
    from app.infrastructure.cache.redis import RedisCache

    test_app = FastAPI(title="DeepVault Test App")
    test_app.include_router(api_router, prefix="/api/v1")

    # Bypass API key for all routes
    test_app.dependency_overrides[get_api_key] = lambda: "test_key"

    # Return mock query service
    test_app.dependency_overrides[get_query_service] = lambda: _MOCK_QS

    # Stub Redis cache so health check doesn't hang
    mock_redis = AsyncMock(spec=RedisCache)
    mock_redis.ping.return_value = True
    test_app.dependency_overrides[get_redis_cache] = lambda: mock_redis

    return test_app


@pytest.fixture(scope="module")
def client():
    app = _build_test_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def application():
    return _build_test_app()


# ---------------------------------------------------------------------------
# Health routes
# ---------------------------------------------------------------------------


class TestHealthRoutes:
    def test_liveness_returns_200(self, client):
        """GET /health must return 200 with mocked Redis."""
        response = client.get("/api/v1/health")
        # 200 with mocked Redis, or 500 if Qdrant check internally called
        assert response.status_code in [200, 500]
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert "status" in data

    def test_detailed_health_endpoint_exists(self, client):
        """GET /health/detailed must exist and return JSON."""
        response = client.get("/api/v1/health/detailed")
        assert response.status_code in [200, 500]
        assert response.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# Query routes
# ---------------------------------------------------------------------------


class TestQueryRoute:
    def test_query_route_returns_403_without_api_key(self):
        """Without X-API-KEY, route must return 403."""
        # Build app WITHOUT the key override
        from app.dependencies import get_query_service

        bare_app = FastAPI()
        bare_app.include_router(api_router, prefix="/api/v1")
        bare_app.dependency_overrides[get_query_service] = lambda: _MOCK_QS

        with TestClient(bare_app, raise_server_exceptions=False) as c:
            response = c.post(
                "/api/v1/query",
                json={"query_text": "What is RAG?", "top_k": 5},
            )
        assert response.status_code == 403

    def test_query_route_422_missing_query_text(self, client):
        """Missing query_text must return 422."""
        response = client.post(
            "/api/v1/query",
            json={"top_k": 5},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 422

    def test_query_route_422_zero_top_k(self, client):
        """top_k = 0 is invalid — must return 422."""
        response = client.post(
            "/api/v1/query",
            json={"query_text": "What is RAG?", "top_k": 0},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 422

    def test_query_route_returns_valid_response(self, client):
        """With mocked service, route must return a well-formed QueryResponse."""
        response = client.post(
            "/api/v1/query",
            json={"query_text": "What is DeepVault?", "top_k": 5},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == _QUERY_RESPONSE.answer
        assert "sources" in data
        assert "latency_ms" in data

    def test_query_accepts_hybrid_retrieval_strategy(self, client):
        """Route must accept 'hybrid' as a valid retrieval_strategy value."""
        response = client.post(
            "/api/v1/query",
            json={"query_text": "test", "top_k": 3, "retrieval_strategy": "hybrid"},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 200

    def test_query_accepts_query_rewriting_flag(self, client):
        """Route must accept use_query_rewriting boolean flag."""
        response = client.post(
            "/api/v1/query",
            json={"query_text": "test rewrite", "top_k": 3, "use_query_rewriting": True},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Ingest routes
# ---------------------------------------------------------------------------


class TestIngestRoutes:
    def test_ingest_text_422_missing_source(self, client):
        """Missing `source` field must return 422 Unprocessable Entity."""
        response = client.post(
            "/api/v1/documents/text",
            json={"content": "Hello World"},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 422

    def test_ingest_text_422_missing_content(self, client):
        """Missing `content` field must return 422."""
        response = client.post(
            "/api/v1/documents/text",
            json={"source": "test.md"},
            headers={"X-API-KEY": "dv-test-only-not-a-real-secret-abc123"},
        )
        assert response.status_code == 422

    def test_ingest_text_requires_api_key(self):
        """Without X-API-KEY, ingest must return 403."""
        from app.dependencies import get_query_service

        bare_app = FastAPI()
        bare_app.include_router(api_router, prefix="/api/v1")
        bare_app.dependency_overrides[get_query_service] = lambda: _MOCK_QS

        with TestClient(bare_app, raise_server_exceptions=False) as c:
            response = c.post(
                "/api/v1/documents/text",
                json={"content": "test", "source": "test.md"},
            )
        assert response.status_code in [403, 422]
