from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.schemas.responses import QueryAPIResponse, SourceChunk
from app.core.models.document import Document, DocumentMetadata
from app.dependencies import get_document_service, get_ingestion_service, get_query_service
from app.main import app

# --- Mock Services ---


@pytest.fixture
def mock_ingestion_svc():
    svc = AsyncMock()
    # Return a dummy document
    doc = Document(
        id="test-doc-id",
        content="Test content",
        metadata=DocumentMetadata(source="test.txt"),
        hash="hashxyz",
    )
    svc.ingest_text.return_value = doc
    svc.ingest_file.return_value = doc
    return svc


@pytest.fixture
def mock_query_svc():
    svc = AsyncMock()
    # Return a dummy query response
    svc.ask.return_value = QueryAPIResponse(
        answer="This is a test answer.",
        sources=[SourceChunk(content="chunk1", document_id="doc1", chunk_index=0, metadata={"source": "test.txt"})],
        latency_ms=42.0,
        request_id="req-123",
    )
    return svc


@pytest.fixture
def mock_document_svc():
    svc = AsyncMock()
    svc.list_documents.return_value = [
        Document(
            id="test-doc-id",
            content="test",
            metadata=DocumentMetadata(source="test.txt"),
            hash="h1",
        )
    ]
    return svc


# --- App override fixture ---


@pytest_asyncio.fixture
async def test_client(mock_ingestion_svc, mock_query_svc, mock_document_svc):
    # Override dependencies
    app.dependency_overrides[get_ingestion_service] = lambda: mock_ingestion_svc
    app.dependency_overrides[get_query_service] = lambda: mock_query_svc
    app.dependency_overrides[get_document_service] = lambda: mock_document_svc

    # We must patch initialize_all, shutdown_all, and AsyncQdrantClient to avoid hitting real DBs during tests
    with (
        patch("app.main.initialize_all", new_callable=AsyncMock),
        patch("app.main.shutdown_all", new_callable=AsyncMock),
        patch("app.infrastructure.stores.qdrant.AsyncQdrantClient", autospec=True),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()


# --- Integration Tests ---


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_ingest_and_query(test_client, mock_ingestion_svc, mock_query_svc):
    # Ingest
    resp_ingest = await test_client.post(
        "/api/v1/documents/text", json={"content": "DeepVault is awesome.", "source": "test"}
    )
    assert resp_ingest.status_code == 200
    assert resp_ingest.json()["document_id"] == "test-doc-id"
    mock_ingestion_svc.ingest_text.assert_awaited_once()

    # Query
    resp_query = await test_client.post("/api/v1/query", json={"query_text": "Is DeepVault awesome?", "top_k": 3})
    assert resp_query.status_code == 200
    data = resp_query.json()
    assert data["answer"] == "This is a test answer."
    assert len(data["sources"]) == 1
    mock_query_svc.ask.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_duplicate_idempotent(test_client, mock_ingestion_svc):
    from app.core.exceptions import DuplicateDocumentError

    mock_ingestion_svc.ingest_text.side_effect = DuplicateDocumentError("Already exists", detail={"source": "test.txt"})

    resp = await test_client.post("/api/v1/documents/text", json={"content": "duplicate content", "source": "test"})
    assert resp.status_code == 200
    assert resp.json()["already_existed"] is True
    assert resp.json()["document_id"] == ""


@pytest.mark.asyncio
async def test_delete_document(test_client, mock_document_svc):
    resp = await test_client.delete("/api/v1/documents/doc-123")
    assert resp.status_code == 204
    mock_document_svc.delete_document.assert_awaited_once_with("doc-123")


@pytest.mark.asyncio
async def test_list_documents_pagination(test_client, mock_document_svc):
    resp = await test_client.get("/api/v1/documents?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["documents"]) == 1
    mock_document_svc.list_documents.assert_awaited_once_with(limit=2, offset=0)
