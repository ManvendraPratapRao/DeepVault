"""
Query Classifier — classifies incoming user queries into one of four types
to enable intelligent routing to the optimal retrieval strategy.

Query Types:
    factual     — Has a single, specific, verifiable answer.
                  e.g., "What is the capital of France?", "What is HNSW?"
    semantic    — Requires conceptual understanding / meaning.
                  e.g., "How does attention work in transformers?", "Explain RAG"
    comparison  — Asks to compare two or more things.
                  e.g., "What are the differences between BM25 and vector search?"
    complex     — Multi-part, analytical, or requires decomposition.
                  e.g., "What are the trade-offs of hybrid retrieval and when should I use reranking?"
"""

import re

from app.infrastructure.logging.structured import logger

# ---------------------------------------------------------------------------
# Query type constants
# ---------------------------------------------------------------------------

FACTUAL = "factual"
SEMANTIC = "semantic"
COMPARISON = "comparison"
COMPLEX = "complex"

QUERY_TYPES = [FACTUAL, SEMANTIC, COMPARISON, COMPLEX]

# ---------------------------------------------------------------------------
# Signal patterns (rule-based, order matters — first match wins)
# ---------------------------------------------------------------------------

_COMPARISON_PATTERNS = [
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bdifference[s]?\b",
    r"\bdifferent\b",
    r"\bbetter\b",
    r"\bworse\b",
    r"\bpros? and cons?\b",
    r"\btrade.?off[s]?\b",
    r"\badvantage[s]?\b.*\bdisadvantage[s]?\b",
    r"\bwhich (is|are|one)\b",
]

_FACTUAL_PATTERNS = [
    r"^what is\b",
    r"^what are\b",
    r"^who (is|was|are|were)\b",
    r"^when (did|was|is|are)\b",
    r"^where (is|was|are|were)\b",
    r"^define\b",
    r"^what does .+ (mean|stand for)\b",
    r"^how many\b",
    r"^how much\b",
    r"^list (the|all)?\b",
    r"^name (the|all)?\b",
]

_COMPLEX_PATTERNS = [
    r"\band\b.+\band\b",            # Multiple conjunctions → multi-part
    r"\?.*\?",                       # Multiple question marks in query
    r"\bfirst\b.+\bthen\b",         # Sequential reasoning
    r"\bstep[s]?\b",
    r"\bbreakdown\b",
    r"\banalyze\b",
    r"\banalyze\b",
    r"\bin what (ways?|circumstances?)\b",
    r"\bunder what conditions?\b",
    r"\bgiven (that|the fact)\b",
]

_SEMANTIC_PATTERNS = [
    r"^how does\b",
    r"^how do\b",
    r"^explain\b",
    r"^why\b",
    r"^what (happens?|occurs?)\b",
    r"\bwork[s]?\b",
    r"\bfunction[s]?\b",
    r"\bbehave[s]?\b",
    r"\bunderstand\b",
    r"\bintuition\b",
]


def _matches(text: str, patterns: list[str]) -> bool:
    """Returns True if any pattern matches the lowercased text."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _count_words(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------------------
# Public classifier
# ---------------------------------------------------------------------------


class QueryClassifier:
    """
    Rule-based query classifier.

    Priority order (highest to lowest specificity):
        1. COMPARISON  — explicit compare/vs/difference signals
        2. COMPLEX     — multi-part, analytical, or long queries (>20 words with conjunctions)
        3. FACTUAL     — starts with "what is", "who is", "define", etc.
        4. SEMANTIC    — "how does", "why", "explain", etc.
        5. SEMANTIC    — fallback (everything else benefits from semantic search)
    """

    def classify(self, query: str) -> str:
        """
        Classifies a query into one of: 'factual', 'semantic', 'comparison', 'complex'.

        Args:
            query: Raw user query string.

        Returns:
            One of QUERY_TYPES constants.
        """
        q = query.strip()

        # --- 1. Comparison (highest priority — very specific signals) ---
        if _matches(q, _COMPARISON_PATTERNS):
            logger.debug(f"Query classified as COMPARISON: '{q[:60]}'")
            return COMPARISON

        # --- 2. Complex (multi-part or analytically heavy) ---
        word_count = _count_words(q)
        is_long = word_count > 20
        has_multiple_conjunctions = len(re.findall(r"\b(and|also|additionally|furthermore|moreover)\b", q, re.IGNORECASE)) >= 2

        if _matches(q, _COMPLEX_PATTERNS) or (is_long and has_multiple_conjunctions):
            logger.debug(f"Query classified as COMPLEX: '{q[:60]}' ({word_count} words)")
            return COMPLEX

        # --- 3. Factual (specific short-answer questions) ---
        if _matches(q, _FACTUAL_PATTERNS):
            logger.debug(f"Query classified as FACTUAL: '{q[:60]}'")
            return FACTUAL

        # --- 4. Semantic (conceptual / reasoning queries) ---
        if _matches(q, _SEMANTIC_PATTERNS):
            logger.debug(f"Query classified as SEMANTIC: '{q[:60]}'")
            return SEMANTIC

        # --- 5. Fallback: default to semantic (benefits from dense vector search) ---
        logger.debug(f"Query defaulting to SEMANTIC: '{q[:60]}'")
        return SEMANTIC
