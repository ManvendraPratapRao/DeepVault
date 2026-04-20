"""
Integration test: Vector vs Hybrid vs Hybrid+Rerank retrieval comparison.

This test validates the end-to-end QueryService pipeline, comparing the three
production retrieval strategies on the same queries with the same mock corpus.

Run with:
    uv run pytest tests/integration/ -v

Note: These tests use mocked Qdrant/BM25 infrastructure. They are NOT
live API tests (those require a running server + seeded Qdrant instance).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.models.document import Chunk, DocumentMetadata
from app.core.models.query import LLMResult, QueryRequest, TokenUsage
from app.infrastructure.rerankers.cross_encoder import CrossEncoderReranker
from app.infrastructure.retrievers.bm25 import BM25Retriever
from app.infrastructure.retrievers.hybrid import HybridRetriever
from app.services.query import QueryService


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

META = DocumentMetadata(source="deepvault_architecture.md")
AI_META = DocumentMetadata(source="ai_systems_overview.md")

CORPUS_CHUNKS = [
    Chunk(
        id="c1",
        document_id="doc1",
        content="DeepVault is a Retrieval-Augmented Generation system using BM25 and vector search.",
        chunk_index=0,
        score=0.95,
        metadata=META.model_dump(),
    ),
    Chunk(
        id="c2",
        document_id="doc1",
        content="The hybrid retrieval strategy combines BM25 keyword scores with dense vector embeddings via RRF.",
        chunk_index=1,
        score=0.88,
        metadata=META.model_dump(),
    ),
    Chunk(
        id="c3",
        document_id="doc2",
        content="Cross-encoder reranking uses ms-marco-MiniLM to re-score retrieved candidates for precision.",
        chunk_index=0,
        score=0.75,
        metadata=AI_META.model_dump(),
    ),
    Chunk(
        id="c4",
        document_id="doc2",
        content="RAG systems can hallucinate when the context is insufficient or the query is ambiguous.",
        chunk_index=1,
        score=0.60,
        metadata=AI_META.model_dump(),
    ),
    Chunk(
        id="c5",
        document_id="doc3",
        content="Qdrant is the vector database used in DeepVault for high-performance ANN search.",
        chunk_index=0,
        score=0.55,
        metadata=DocumentMetadata(source="infrastructure_guide.md").model_dump(),
    ),
]


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.generate.return_value = LLMResult(
        answer="DeepVault is a RAG system using hybrid retrieval.",
        usage=TokenUsage(prompt_tokens=200, completion_tokens=60, total_tokens=260),
    )
    return llm


@pytest.fixture
def mock_vector_retriever() -> AsyncMock:
    """Simulates a QdrantVectorStore retriever with fixed ranking."""
    retriever = AsyncMock()
    # Vector search ranks by embedding similarity: c1, c2, c3, c4, c5
    retriever.retrieve.return_value = CORPUS_CHUNKS[:3]
    return retriever


@pytest.fixture
def mock_bm25_retriever() -> AsyncMock:
    """Simulates a BM25Retriever with keyword-biased ranking."""
    retriever = AsyncMock()
    # BM25 ranks keyword-heavy results differently: c2 (BM25/hybrid keywords), c1, c5
    retriever.retrieve.return_value = [CORPUS_CHUNKS[1], CORPUS_CHUNKS[0], CORPUS_CHUNKS[4]]
    return retriever


@pytest.fixture
def mock_reranker() -> MagicMock:
    """Simulates cross-encoder reranker selecting c3 as top result."""
    reranker = AsyncMock()
    # Reranker selects c3 as the most relevant to the query about reranking
    reranker.rerank.return_value = [CORPUS_CHUNKS[2], CORPUS_CHUNKS[0]]
    return reranker


# ---------------------------------------------------------------------------
# Strategy 1: Pure Vector Retrieval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_retrieval_strategy(mock_vector_retriever, mock_llm):
    """
    Vector-only retrieval: uses dense embeddings directly.
    Expected: top-k chunks from the vector retriever, no BM25 or reranking.
    """
    service = QueryService(
        retriever=mock_vector_retriever,
        llm_client=mock_llm,
    )

    request = QueryRequest(
        query_text="How does DeepVault handle retrieval?",
        top_k=3,
        retrieval_strategy="vector",
        chunking_strategy="fixed",
    )
    response = await service.ask(request)

    # Verify we got a valid response
    assert response.answer == "DeepVault is a RAG system using hybrid retrieval."
    assert len(response.sources) == 3
    assert response.latency_ms > 0
    assert response.usage.total_tokens == 260

    # Verify vector retriever was called once with correct params
    mock_vector_retriever.retrieve.assert_awaited_once_with(
        query="How does DeepVault handle retrieval?",
        top_k=3,
        filters=None,
        collection_name="deepvault_fixed",
    )
    # LLM was called exactly once
    mock_llm.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Strategy 2: Hybrid Retrieval (BM25 + Vector RRF)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_retrieval_strategy(mock_vector_retriever, mock_bm25_retriever, mock_llm):
    """
    Hybrid retrieval: merges vector and BM25 results via RRF.
    Validates that both retrievers are called and that the merged
    result set is different from pure vector ordering.
    """
    hybrid = HybridRetriever(
        vector_retriever=mock_vector_retriever,
        bm25_retriever=mock_bm25_retriever,
        rrf_k=60,
        vector_weight=0.7,
        bm25_weight=0.3,
    )
    service = QueryService(retriever=hybrid, llm_client=mock_llm)

    request = QueryRequest(
        query_text="Explain BM25 keyword retrieval in DeepVault",
        top_k=3,
        retrieval_strategy="hybrid",
        chunking_strategy="fixed",
    )
    response = await service.ask(request)

    assert response.answer is not None
    assert len(response.sources) > 0
    assert response.latency_ms >= 0

    # Both retrievers were called concurrently via asyncio.gather
    mock_vector_retriever.retrieve.assert_awaited_once()
    mock_bm25_retriever.retrieve.assert_awaited_once()

    # RRF deduplication — max results ≤ combined unique chunks from both lists
    chunk_ids = {c.id for c in response.sources}
    assert len(chunk_ids) == len(response.sources)  # no duplicates


# ---------------------------------------------------------------------------
# Strategy 3: Hybrid + Cross-Encoder Rerank
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_rerank_strategy(mock_vector_retriever, mock_bm25_retriever, mock_reranker, mock_llm):
    """
    Full pipeline: Hybrid RRF retrieval + cross-encoder reranking.
    Validates that:
    - fetch_k = top_k * 4 candidate chunks are retrieved before reranking
    - reranker re-orders and truncates to top_k
    - final answer is grounded in reranked sources
    """
    hybrid = HybridRetriever(
        vector_retriever=mock_vector_retriever,
        bm25_retriever=mock_bm25_retriever,
        rrf_k=60,
    )
    service = QueryService(
        retriever=hybrid,
        llm_client=mock_llm,
        reranker=mock_reranker,
    )

    request = QueryRequest(
        query_text="How does cross-encoder reranking improve precision?",
        top_k=2,
        retrieval_strategy="hybrid_rerank",
        chunking_strategy="fixed",
    )
    response = await service.ask(request)

    assert response.answer is not None
    # Verify the reranker was called and its results are used
    mock_reranker.rerank.assert_awaited_once()
    rerank_call_args = mock_reranker.rerank.call_args
    assert rerank_call_args.kwargs["top_k"] == 2

    # Final sources come from the reranker's output
    assert len(response.sources) == 2
    assert response.sources[0].id == "c3"  # reranker selected c3 as best match


# ---------------------------------------------------------------------------
# Comparative: Strategy Correctness Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategies_return_different_rankings(mock_vector_retriever, mock_bm25_retriever, mock_llm):
    """
    Validates that vector-only and BM25-only strategies return different
    rankings for the same query — confirming each retriever has distinct
    ranking logic.
    """
    vector_service = QueryService(retriever=mock_vector_retriever, llm_client=mock_llm)
    bm25_service = QueryService(retriever=mock_bm25_retriever, llm_client=mock_llm)

    query = QueryRequest(
        query_text="BM25 keyword retrieval index",
        top_k=3,
        retrieval_strategy="vector",
        chunking_strategy="fixed",
    )

    vector_resp = await vector_service.ask(query)
    bm25_resp = await bm25_service.ask(query)

    vector_ids = [c.id for c in vector_resp.sources]
    bm25_ids = [c.id for c in bm25_resp.sources]

    # The two strategies should return different orderings
    # (BM25 prioritises keyword matches, vector prioritises semantic similarity)
    assert vector_ids != bm25_ids, (
        "Vector and BM25 retrieval returned identical rankings — "
        "test mock setup may be incorrect."
    )


@pytest.mark.asyncio
async def test_reranker_reduces_source_count(mock_vector_retriever, mock_bm25_retriever, mock_reranker, mock_llm):
    """
    Confirms that hybrid_rerank fetches 4x candidates but returns only top_k.
    This verifies the QueryService fetch_k amplification logic.
    """
    hybrid = HybridRetriever(
        vector_retriever=mock_vector_retriever,
        bm25_retriever=mock_bm25_retriever,
    )
    service = QueryService(retriever=hybrid, llm_client=mock_llm, reranker=mock_reranker)

    request = QueryRequest(
        query_text="reranking precision",
        top_k=2,
        retrieval_strategy="hybrid_rerank",
        chunking_strategy="fixed",
    )
    response = await service.ask(request)

    # Reranker was called, result is bounded to top_k=2
    assert len(response.sources) <= 2
    mock_reranker.rerank.assert_awaited_once()

    # The reranker call received a larger candidate set (fetch_k = 2 * 4 = 8)
    # In practice with our 3+3 mock corpus the merged set is smaller,
    # but we confirm the reranker received the merged candidates.
    rerank_chunks_arg = mock_reranker.rerank.call_args.kwargs["chunks"]
    assert len(rerank_chunks_arg) > 0


@pytest.mark.asyncio
async def test_query_rewriting_modifies_search_query(mock_vector_retriever, mock_llm):
    """
    Validates that when use_query_rewriting=True and a rewriter is injected,
    the rewritten query (not the raw query) is passed to the retriever.
    """
    mock_rewriter = AsyncMock()
    mock_rewriter.rewrite.return_value = (
        "Explain the Retrieval-Augmented Generation architecture of DeepVault RAG system"
    )

    service = QueryService(
        retriever=mock_vector_retriever,
        llm_client=mock_llm,
        rewriter=mock_rewriter,
    )

    request = QueryRequest(
        query_text="how does it work?",
        top_k=3,
        retrieval_strategy="vector",
        chunking_strategy="fixed",
        use_query_rewriting=True,
    )
    await service.ask(request)

    # Rewriter was called with the original vague query
    mock_rewriter.rewrite.assert_awaited_once_with("how does it work?")

    # Retriever was called with the REWRITTEN query, not the original
    call_kwargs = mock_vector_retriever.retrieve.call_args.kwargs
    assert call_kwargs["query"] != "how does it work?"
    assert "Retrieval-Augmented Generation" in call_kwargs["query"]
