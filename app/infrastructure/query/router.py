"""
Query Router — maps a classified query type to the optimal retrieval strategy.

Routing logic is based on Phase 2 benchmark findings (docs/benchmarks/v2.0.0.md):

    factual    → hybrid         BM25 excels at exact-keyword retrieval. Factual questions
                                use specific terminology (product names, acronyms, standards).
                                Hybrid reduces hallucination (28.6% vs 37.5% vector-only).

    semantic   → vector         Pure dense vector search is optimal for conceptual queries.
                                The embedding captures meaning better than keyword overlap.

    comparison → hybrid_rerank  Comparison queries need high recall (many relevant chunks)
                                plus precision reranking to pick the best cross-document pair.
                                Cross-encoder resolves relevance across heterogeneous chunks.

    complex    → hybrid_rerank  Complex multi-part queries benefit from broad retrieval
                                (hybrid catches both semantic and keyword hits) plus
                                cross-encoder reranking to surface the most grounded chunks.

Note: The routing can be overridden by the caller by passing `retrieval_strategy` explicitly.
"""

from app.infrastructure.logging.structured import logger
from app.infrastructure.query.classifier import (
    COMPARISON,
    COMPLEX,
    FACTUAL,
    SEMANTIC,
    QueryClassifier,
)

# ---------------------------------------------------------------------------
# Routing table (query_type → retrieval_strategy)
# ---------------------------------------------------------------------------

_ROUTING_TABLE: dict[str, str] = {
    FACTUAL: "hybrid",           # BM25 + vector: best for exact-term retrieval
    SEMANTIC: "vector",          # Dense vector: best for conceptual understanding
    COMPARISON: "hybrid_rerank", # Need recall + precision for cross-document comparison
    COMPLEX: "hybrid_rerank",    # Need both keyword + semantic, then reranked
}


class QueryRouter:
    """
    Routes a query to the optimal retrieval strategy based on query type.

    Usage:
        router = QueryRouter()
        strategy = router.route("What is BM25?")
        # → "hybrid"

        strategy = router.route("Compare BM25 vs vector search")
        # → "hybrid_rerank"

    The router can be bypassed by the caller passing an explicit retrieval_strategy.
    In that case, QueryService should use the explicit strategy and skip routing.
    """

    def __init__(self, classifier: QueryClassifier | None = None):
        self.classifier = classifier or QueryClassifier()

    def route(self, query: str) -> str:
        """
        Classifies the query and returns the optimal retrieval strategy name.

        Args:
            query: The raw user query string.

        Returns:
            One of: 'vector', 'hybrid', 'hybrid_rerank'
        """
        query_type = self.classifier.classify(query)
        strategy = _ROUTING_TABLE[query_type]

        logger.info(
            f"Query routed: type={query_type} → strategy={strategy}",
            extra={
                "extra_fields": {
                    "query_type": query_type,
                    "routed_strategy": strategy,
                    "query_preview": query[:80],
                }
            },
        )
        return strategy

    def classify_and_route(self, query: str) -> tuple[str, str]:
        """
        Returns both the query type and the routed strategy.
        Useful for logging and benchmark analysis.

        Returns:
            (query_type, retrieval_strategy)
        """
        query_type = self.classifier.classify(query)
        strategy = _ROUTING_TABLE[query_type]
        return query_type, strategy
