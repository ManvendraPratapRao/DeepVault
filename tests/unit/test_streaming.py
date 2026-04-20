"""
Unit tests for QueryService.ask_stream()

Tests the streaming pipeline by mocking the LLM stream and verifying
that tokens are yielded correctly through the full RAG pipeline.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.models.document import Chunk, DocumentMetadata
from app.core.models.query import QueryRequest
from app.services.query import QueryService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_gen(*tokens: str):
    """Helper: async generator that yields a fixed sequence of tokens."""
    for t in tokens:
        yield t


META = DocumentMetadata(source="test_doc.md")
SAMPLE_CHUNKS = [
    Chunk(id="c1", document_id="d1", content="DeepVault is a RAG system.", chunk_index=0, metadata=META.model_dump()),
    Chunk(id="c2", document_id="d1", content="It uses hybrid retrieval.", chunk_index=1, metadata=META.model_dump()),
]


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.retrieve.return_value = SAMPLE_CHUNKS
    return r


@pytest.fixture
def mock_streaming_llm():
    """LLM client whose .stream() returns an async generator of tokens."""
    llm = MagicMock()
    # stream() is a real async generator method — return it from the mock
    llm.stream = MagicMock(return_value=_async_gen("Deep", "Vault", " is", " awesome", "."))
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_stream_yields_tokens(mock_retriever, mock_streaming_llm):
    """ask_stream() should yield each token produced by llm_client.stream()."""
    service = QueryService(retriever=mock_retriever, llm_client=mock_streaming_llm)
    request = QueryRequest(query_text="What is DeepVault?", top_k=2)

    tokens = []
    async for token in service.ask_stream(request):
        tokens.append(token)

    assert len(tokens) == 5  # "Deep", "Vault", " is", " awesome", "."
    assert "".join(tokens) == "DeepVault is awesome."


@pytest.mark.asyncio
async def test_ask_stream_uses_retriever(mock_retriever, mock_streaming_llm):
    """ask_stream() should call the retriever with the correct query."""
    service = QueryService(retriever=mock_retriever, llm_client=mock_streaming_llm)
    request = QueryRequest(query_text="What is RAG?", top_k=3, chunking_strategy="fixed")

    # Consume the generator
    _ = [t async for t in service.ask_stream(request)]

    mock_retriever.retrieve.assert_awaited_once_with(
        query="What is RAG?",
        top_k=3,
        filters=None,
        collection_name="deepvault_fixed",
    )


@pytest.mark.asyncio
async def test_ask_stream_empty_retrieval_yields_error(mock_streaming_llm):
    """When retrieval returns nothing, ask_stream() should yield an [ERROR] token."""
    empty_retriever = AsyncMock()
    empty_retriever.retrieve.return_value = []

    service = QueryService(retriever=empty_retriever, llm_client=mock_streaming_llm)
    request = QueryRequest(query_text="unknown query", top_k=3)

    tokens = [t async for t in service.ask_stream(request)]

    assert len(tokens) == 1
    assert "[ERROR]" in tokens[0]


@pytest.mark.asyncio
async def test_ask_stream_cached_replays_tokens():
    """When a cache hit occurs, ask_stream() should replay the cached answer word-by-word."""
    from app.core.models.query import QueryResponse, TokenUsage

    cached_response = QueryResponse(
        answer="This is a cached answer.",
        sources=[],
        usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        latency_ms=5.0,
        request_id="cached-req",
    )

    mock_cache = AsyncMock()
    mock_cache.get_cached_response.return_value = cached_response

    service = QueryService(
        retriever=AsyncMock(),
        llm_client=MagicMock(),
        cache_service=mock_cache,
    )
    request = QueryRequest(query_text="What is DeepVault?", top_k=3)

    tokens = [t async for t in service.ask_stream(request)]

    # Cache replays word-by-word — "This ", "is ", "a ", "cached ", "answer. "
    full = "".join(tokens).strip()
    assert "cached answer" in full


@pytest.mark.asyncio
async def test_ask_stream_reranking_applied():
    """With hybrid_rerank strategy and a reranker, reranker.rerank() is called before streaming."""
    mock_retriever = AsyncMock()
    mock_retriever.retrieve.return_value = SAMPLE_CHUNKS

    mock_reranker = AsyncMock()
    mock_reranker.rerank.return_value = [SAMPLE_CHUNKS[0]]  # Reranker picks top-1

    mock_llm = MagicMock()
    mock_llm.stream = MagicMock(return_value=_async_gen("Answer"))

    service = QueryService(
        retriever=mock_retriever,
        llm_client=mock_llm,
        reranker=mock_reranker,
    )
    request = QueryRequest(
        query_text="Explain reranking",
        top_k=1,
        retrieval_strategy="hybrid_rerank",
        chunking_strategy="fixed",
    )

    _ = [t async for t in service.ask_stream(request)]

    # Reranker should have been called
    mock_reranker.rerank.assert_awaited_once()
    rerank_call = mock_reranker.rerank.call_args.kwargs
    assert rerank_call["top_k"] == 1
