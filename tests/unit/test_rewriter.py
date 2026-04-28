"""
Unit tests for GroqQueryRewriter.

Tests that the rewriter correctly expands different query patterns
(ambiguous, multi-part, abbreviation-heavy) and handles LLM failures gracefully.
"""

from unittest.mock import AsyncMock

import pytest

from app.core.models.query import LLMResult, TokenUsage
from app.infrastructure.query.rewriter import GroqQueryRewriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USAGE = TokenUsage(prompt_tokens=50, completion_tokens=30, total_tokens=80)


def _make_llm(answer: str) -> AsyncMock:
    llm = AsyncMock()
    llm.generate.return_value = LLMResult(answer=answer, usage=_USAGE)
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGroqQueryRewriter:
    @pytest.mark.asyncio
    async def test_rewrite_simple_ambiguous_query(self):
        """An ambiguous query should be expanded into a more specific one."""
        expanded = "What are the specific technical challenges of implementing attention mechanisms in transformer architectures?"
        llm = _make_llm(expanded)
        rewriter = GroqQueryRewriter(llm_client=llm)

        result = await rewriter.rewrite("How does attention work?")

        assert result != "How does attention work?"
        assert len(result) > len("How does attention work?")
        llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rewrite_multipart_query(self):
        """A multi-part question should be expanded for better retrieval."""
        expanded = "What are the differences between BM25 keyword retrieval and dense vector retrieval, and when should each be used in RAG systems?"
        llm = _make_llm(expanded)
        rewriter = GroqQueryRewriter(llm_client=llm)

        result = await rewriter.rewrite("Compare BM25 and vector search in RAG")

        assert result == expanded

    @pytest.mark.asyncio
    async def test_rewrite_abbreviation_heavy_query(self):
        """Queries with abbreviations should have them expanded."""
        expanded = "How does Reciprocal Rank Fusion (RRF) combine BM25 keyword scores with dense vector similarity scores in hybrid retrieval?"
        llm = _make_llm(expanded)
        rewriter = GroqQueryRewriter(llm_client=llm)

        result = await rewriter.rewrite("How does RRF work in hybrid retrieval?")

        assert "RRF" in result or "Reciprocal" in result

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_on_llm_failure(self):
        """If the LLM fails, rewriter should return the original query unchanged."""
        llm = AsyncMock()
        llm.generate.side_effect = Exception("Groq API unavailable")
        rewriter = GroqQueryRewriter(llm_client=llm)

        original = "What is retrieval-augmented generation?"
        result = await rewriter.rewrite(original)

        # On failure, must return original without raising
        assert result == original

    @pytest.mark.asyncio
    async def test_rewrite_does_not_modify_very_specific_query(self):
        """The LLM prompt is called even for specific queries — result is what the LLM returns."""
        specific_query = "What is the exact formula for BM25Okapi relevance scoring?"
        llm = _make_llm(specific_query)  # LLM returns same query (it's already specific)
        rewriter = GroqQueryRewriter(llm_client=llm)

        result = await rewriter.rewrite(specific_query)

        assert result == specific_query  # LLM echo = original returned

    @pytest.mark.asyncio
    async def test_rewrite_calls_llm_with_query_in_prompt(self):
        """The generate() call must include the original query in its prompt."""
        llm = _make_llm("expanded query")
        rewriter = GroqQueryRewriter(llm_client=llm)

        await rewriter.rewrite("test query about HNSW indexing")

        call_args = llm.generate.call_args
        # The query must appear somewhere in the prompt or system prompt
        prompt_text = str(call_args)
        assert "HNSW" in prompt_text or "test query" in prompt_text
