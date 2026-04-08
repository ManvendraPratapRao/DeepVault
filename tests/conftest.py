from unittest.mock import AsyncMock

import pytest

from app.core.models.document import Chunk, Document, DocumentMetadata


@pytest.fixture
def sample_document():
    return Document(
        id="doc-123",
        content="This is a sample document for testing logic. It contains multiple sentences. Hopefully it works.",
        metadata=DocumentMetadata(source="test.md", author="Test Author"),
        hash="test-hash-123",
    )


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            id="chunk-1",
            document_id="doc-123",
            content="This is a sample document for testing logic.",
            chunk_index=0,
            embedding=[0.1] * 384,
            metadata={"source": "test.md"},
        ),
        Chunk(
            id="chunk-2",
            document_id="doc-123",
            content="It contains multiple sentences.",
            chunk_index=1,
            embedding=[0.2] * 384,
            metadata={"source": "test.md"},
        ),
        Chunk(
            id="chunk-3",
            document_id="doc-123",
            content="Hopefully it works.",
            chunk_index=2,
            embedding=[0.3] * 384,
            metadata={"source": "test.md"},
        ),
    ]


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed_text.return_value = [0.1] * 384
    embedder.embed_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
    embedder.get_dimension.return_value = 384
    return embedder


@pytest.fixture
def mock_llm_client():
    llm = AsyncMock()
    llm.generate.return_value = "This is a mocked LLM answer."
    return llm


@pytest.fixture
def mock_doc_store(sample_document):
    store = AsyncMock()
    # By default, mock getting a document to return the sample
    store.get_document.return_value = sample_document
    # Mock list to return a single document
    store.list_documents.return_value = [sample_document]
    return store


@pytest.fixture
def mock_retriever(sample_chunks):
    retriever = AsyncMock()
    retriever.retrieve.return_value = sample_chunks
    return retriever


@pytest.fixture
def mock_vector_store(sample_chunks):
    store = AsyncMock()
    # Let's not define retrieve output here, it's tied to retrievers,
    # but let's just make it an AsyncMock.
    return store
