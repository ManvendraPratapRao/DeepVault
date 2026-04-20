from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.models.document import Chunk, DocumentMetadata
from app.infrastructure.rerankers.cross_encoder import CrossEncoderReranker
from app.infrastructure.retrievers.bm25 import BM25Retriever
from app.infrastructure.retrievers.hybrid import HybridRetriever


@pytest.fixture
def mock_qdrant():
    return AsyncMock()


@pytest.fixture
def sample_chunks():
    meta = DocumentMetadata(source="test.md")
    return [
        Chunk(
            id="1", document_id="doc1", content="DeepVault is an AI system.", chunk_index=0, metadata=meta.model_dump()
        ),
        Chunk(
            id="2", document_id="doc1", content="It uses RAG for retrieval.", chunk_index=1, metadata=meta.model_dump()
        ),
        Chunk(id="3", document_id="doc2", content="BM25 is keyword based.", chunk_index=0, metadata=meta.model_dump()),
    ]


@pytest.mark.asyncio
async def test_bm25_retriever_initialization(mock_qdrant, sample_chunks):
    # Mock Qdrant scroll response
    mock_qdrant.scroll.return_value = (
        [
            MagicMock(
                id=c.id,
                payload={
                    "content": c.content,
                    "document_id": c.document_id,
                    "chunk_index": c.chunk_index,
                    "metadata": c.metadata,
                },
            )
            for c in sample_chunks
        ],
        None,
    )

    retriever = BM25Retriever(qdrant_client=mock_qdrant)
    await retriever.initialize("test_collection")

    assert "test_collection" in retriever._indexes
    assert len(retriever._corpus["test_collection"]) == 3


@pytest.mark.asyncio
async def test_bm25_search_scoring(mock_qdrant, sample_chunks):
    mock_qdrant.scroll.return_value = (
        [
            MagicMock(
                id=c.id,
                payload={
                    "content": c.content,
                    "document_id": c.document_id,
                    "chunk_index": c.chunk_index,
                    "metadata": c.metadata,
                },
            )
            for c in sample_chunks
        ],
        None,
    )
    retriever = BM25Retriever(qdrant_client=mock_qdrant)

    # Query for "BM25" should rank chunk 3 first
    results = await retriever.retrieve("BM25 retrieval", top_k=1, collection_name="test_collection")

    assert len(results) == 1
    assert "BM25" in results[0].content


@pytest.mark.asyncio
async def test_rrf_merging_logic():
    v_retriever = AsyncMock()
    b_retriever = AsyncMock()

    c1 = Chunk(id="A", document_id="D1", content="A", chunk_index=0)
    c2 = Chunk(id="B", document_id="D1", content="B", chunk_index=1)

    # Vector ranks [A, B]
    v_retriever.retrieve.return_value = [c1, c2]
    # BM25 ranks [B, A]
    b_retriever.retrieve.return_value = [c2, c1]

    hybrid = HybridRetriever(v_retriever, b_retriever, rrf_k=1)
    results = await hybrid.retrieve("test", top_k=2, collection_name="test")

    # In RRF with k=1:
    # A score = (1 / (1+0+1)) + (1 / (1+1+1)) = 0.5 + 0.33 = 0.83
    # B score = (1 / (1+1+1)) + (1 / (1+0+1)) = 0.33 + 0.5 = 0.83
    # They should both be in the results
    assert len(results) == 2
    assert {r.id for r in results} == {"A", "B"}


@pytest.mark.asyncio
async def test_cross_encoder_reranker_mocked():
    # Mocking the actual model load because it's heavy
    with MagicMock() as mock_ce:
        # Manually patch the CrossEncoder class in the module
        import app.infrastructure.rerankers.cross_encoder as ce_mod

        original_ce = ce_mod.CrossEncoder
        ce_mod.CrossEncoder = MagicMock(return_value=mock_ce)

        # Mock scores: [low, high] for chunks [1, 2]
        mock_ce.predict.return_value = [0.1, 0.9]

        reranker = CrossEncoderReranker(model_name="mock")

        chunks = [
            Chunk(id="1", document_id="D", content="Low relevance", chunk_index=0),
            Chunk(id="2", document_id="D", content="High relevance", chunk_index=1),
        ]

        results = await reranker.rerank("query", chunks, top_k=1)

        assert len(results) == 1
        assert results[0].id == "2"

        # Restore original
        ce_mod.CrossEncoder = original_ce
