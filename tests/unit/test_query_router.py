"""
Unit tests for QueryClassifier and QueryRouter (Phase 3).

Tests 25+ query patterns covering all 4 classification categories,
boundary conditions, and routing table correctness.
"""

import pytest

from app.infrastructure.query.classifier import (
    COMPARISON,
    COMPLEX,
    FACTUAL,
    SEMANTIC,
    QueryClassifier,
)
from app.infrastructure.query.router import QueryRouter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def classifier():
    return QueryClassifier()


@pytest.fixture
def router():
    return QueryRouter()


# ---------------------------------------------------------------------------
# QueryClassifier — FACTUAL queries
# ---------------------------------------------------------------------------


class TestFactualClassification:
    def test_what_is_basic(self, classifier):
        assert classifier.classify("What is BM25?") == FACTUAL

    def test_what_are_basic(self, classifier):
        assert classifier.classify("What are the chunking strategies in DeepVault?") == FACTUAL

    def test_define_keyword(self, classifier):
        assert classifier.classify("Define retrieval-augmented generation") == FACTUAL

    def test_who_is(self, classifier):
        assert classifier.classify("Who is the author of the BM25 paper?") == FACTUAL

    def test_how_many(self, classifier):
        assert classifier.classify("How many chunks does sliding window chunking produce?") == FACTUAL

    def test_list_query(self, classifier):
        assert classifier.classify("List the supported file types in DeepVault") == FACTUAL

    def test_name_query(self, classifier):
        assert classifier.classify("Name the retrieval strategies available") == FACTUAL

    def test_what_does_mean(self, classifier):
        assert classifier.classify("What does HNSW stand for?") == FACTUAL


# ---------------------------------------------------------------------------
# QueryClassifier — SEMANTIC queries
# ---------------------------------------------------------------------------


class TestSemanticClassification:
    def test_how_does_work(self, classifier):
        assert classifier.classify("How does attention work in transformers?") == SEMANTIC

    def test_explain(self, classifier):
        assert classifier.classify("Explain the concept of reciprocal rank fusion") == SEMANTIC

    def test_why_query(self, classifier):
        assert classifier.classify("Why does semantic chunking use embedding similarity?") == SEMANTIC

    def test_how_do_embeddings(self, classifier):
        assert classifier.classify("How do embeddings capture semantic meaning?") == SEMANTIC

    def test_fallback_open_query(self, classifier):
        """An unclassified open question should default to SEMANTIC."""
        result = classifier.classify("Tell me about vector databases")
        assert result == SEMANTIC


# ---------------------------------------------------------------------------
# QueryClassifier — COMPARISON queries
# ---------------------------------------------------------------------------


class TestComparisonClassification:
    def test_vs_keyword(self, classifier):
        assert classifier.classify("BM25 vs vector search: which is better?") == COMPARISON

    def test_compare_keyword(self, classifier):
        assert classifier.classify("Compare the sliding and recursive window chunking strategies") == COMPARISON

    def test_differences_keyword(self, classifier):
        assert classifier.classify("What are the differences between hybrid and vector retrieval?") == COMPARISON

    def test_versus_keyword(self, classifier):
        assert classifier.classify("Dense retrieval versus sparse retrieval — tradeoffs?") == COMPARISON

    def test_which_is_better(self, classifier):
        assert classifier.classify("Which is better: reranking or hybrid retrieval?") == COMPARISON

    def test_trade_offs(self, classifier):
        assert classifier.classify("What are the trade-offs of cross-encoder reranking?") == COMPARISON

    def test_pros_and_cons(self, classifier):
        assert classifier.classify("What are the pros and cons of in-memory BM25?") == COMPARISON


# ---------------------------------------------------------------------------
# QueryClassifier — COMPLEX queries
# ---------------------------------------------------------------------------


class TestComplexClassification:
    def test_multi_part_with_and(self, classifier):
        query = "How does hybrid retrieval work and when should I use reranking and what are the latency implications?"
        assert classifier.classify(query) == COMPLEX

    def test_step_by_step(self, classifier):
        assert classifier.classify("Describe the step-by-step process of ingesting a PDF document") == COMPLEX

    def test_analyze_query(self, classifier):
        assert classifier.classify("Analyze the performance characteristics of BM25 on enterprise documents") == COMPLEX

    def test_breakdown_query(self, classifier):
        assert classifier.classify("Give me a breakdown of the evaluation metrics used in DeepVault") == COMPLEX


# ---------------------------------------------------------------------------
# QueryRouter — routing correctness
# ---------------------------------------------------------------------------


class TestQueryRouter:
    def test_factual_routes_to_hybrid(self, router):
        """Factual queries → hybrid (BM25 excels at exact-keyword retrieval)."""
        strategy = router.route("What is BM25?")
        assert strategy == "hybrid"

    def test_semantic_routes_to_vector(self, router):
        """Semantic queries → vector (dense embeddings capture conceptual meaning)."""
        strategy = router.route("How does attention work?")
        assert strategy == "vector"

    def test_comparison_routes_to_hybrid_rerank(self, router):
        """Comparison queries → hybrid_rerank (need recall + reranking precision)."""
        strategy = router.route("Compare BM25 vs vector search")
        assert strategy == "hybrid_rerank"

    def test_complex_routes_to_hybrid_rerank(self, router):
        """Complex queries → hybrid_rerank (multi-aspect needs broad retrieval + reranking)."""
        strategy = router.route("How does hybrid retrieval work and what are the implications for latency and cost?")
        assert strategy == "hybrid_rerank"

    def test_classify_and_route_returns_both(self, router):
        """classify_and_route() must return both type and strategy."""
        query_type, strategy = router.classify_and_route("What is RAG?")
        assert query_type in ["factual", "semantic", "comparison", "complex"]
        assert strategy in ["vector", "hybrid", "hybrid_rerank"]

    def test_router_uses_custom_classifier(self):
        """Router correctly delegates to an injected classifier."""
        from unittest.mock import MagicMock

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = FACTUAL

        router = QueryRouter(classifier=mock_classifier)
        strategy = router.route("any query")

        mock_classifier.classify.assert_called_once_with("any query")
        assert strategy == "hybrid"  # FACTUAL → hybrid per routing table
