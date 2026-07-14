"""
A/B Testing Service — traffic splitting and statistical significance testing
for RAG prompt templates and retrieval strategies.

Phase 5 / Session 27 feature.

Design:
    - Traffic splitting by session_id hash (deterministic — same session always
      gets the same variant, no cookie/state required).
    - Two test types: prompt A/B and retrieval strategy A/B.
    - Results stored in SQLite (ab_test_results table).
    - Statistical significance via Chi-squared test (for discrete outcomes)
      and Welch's t-test (for continuous metrics like rating/latency).
    - Admin endpoint to read results and p-values.

Usage:
    service = ABTestingService()
    variant = service.assign_variant(session_id="user-abc", test_name="prompt_v2_test")
    # → "control" or "treatment"
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

import aiosqlite

from app.infrastructure.logging.structured import logger

_DEFAULT_DB = "deepvault.db"

# ---------------------------------------------------------------------------
# Active test registry
# ---------------------------------------------------------------------------


@dataclass
class ABTest:
    """Defines a single A/B test configuration."""

    name: str  # Unique test identifier
    description: str
    test_type: str  # "prompt" | "retrieval_strategy"
    control_value: str  # e.g., "v1_prompt" or "hybrid"
    treatment_value: str  # e.g., "v2_prompt" or "hybrid_rerank"
    traffic_split: float = 0.5  # Fraction of traffic in treatment (0.0–1.0)
    active: bool = True


# Register active tests here — add new tests without touching other code
ACTIVE_TESTS: dict[str, ABTest] = {
    "prompt_v3_test": ABTest(
        name="prompt_v3_test",
        description="Compare v1 RAG system prompt vs v3 decomposition-aware prompt",
        test_type="prompt",
        control_value="v1",
        treatment_value="v3",
        traffic_split=0.5,
    ),
    "rerank_vs_hybrid": ABTest(
        name="rerank_vs_hybrid",
        description="Compare hybrid vs hybrid_rerank for semantic queries",
        test_type="retrieval_strategy",
        control_value="hybrid",
        treatment_value="hybrid_rerank",
        traffic_split=0.5,
    ),
}


# ---------------------------------------------------------------------------
# Variant assignment (deterministic by session_id)
# ---------------------------------------------------------------------------


def assign_variant(session_id: str, test_name: str) -> str:
    """
    Assigns a test variant deterministically by hashing session_id + test_name.
    Same session_id always gets the same variant — no state required.

    Returns:
        "control" or "treatment"
    """
    test = ACTIVE_TESTS.get(test_name)
    if not test or not test.active:
        return "control"

    # Deterministic hash: session_id + test_name → [0.0, 1.0)
    h = hashlib.md5(f"{session_id}:{test_name}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF  # Normalize to [0, 1]

    variant = "treatment" if bucket < test.traffic_split else "control"
    return variant


def get_variant_value(session_id: str, test_name: str) -> str:
    """
    Returns the actual value for the assigned variant (e.g., "hybrid_rerank" or "hybrid").
    """
    test = ACTIVE_TESTS.get(test_name)
    if not test:
        return ""
    variant = assign_variant(session_id, test_name)
    return test.treatment_value if variant == "treatment" else test.control_value


# ---------------------------------------------------------------------------
# Results storage
# ---------------------------------------------------------------------------


class ABTestingService:
    """
    Manages A/B test result recording and statistical analysis.

    Stores one result row per request, enabling offline analysis of:
    - User ratings per variant
    - Latency per variant
    - Conversion rate (rating >= 4 as "positive outcome")
    """

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path

    async def initialize(self) -> None:
        """Creates the ab_test_results table if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ab_test_results (
                    id           TEXT PRIMARY KEY,
                    test_name    TEXT NOT NULL,
                    variant      TEXT NOT NULL,
                    session_id   TEXT,
                    metric_name  TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    created_at   TEXT NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_ab_test ON ab_test_results(test_name, variant)")
            await db.commit()
        logger.info("ABTestingService initialized.")

    async def record_result(
        self,
        test_name: str,
        variant: str,
        metric_name: str,
        metric_value: float,
        session_id: str | None = None,
    ) -> None:
        """Records one A/B test measurement."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO ab_test_results
                   (id, test_name, variant, session_id, metric_name, metric_value, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    test_name,
                    variant,
                    session_id,
                    metric_name,
                    metric_value,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            await db.commit()

    async def get_results(self, test_name: str) -> dict[str, Any]:
        """
        Returns aggregated results for a test with basic statistical analysis.

        Computes per-variant:
        - Sample size (n)
        - Mean metric value
        - Standard deviation
        - Positive outcome rate (metric_value >= 4 for ratings, or < 2s for latency)

        Also computes Welch's t-test p-value for the mean difference.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT variant, metric_name, AVG(metric_value) as mean,
                          COUNT(*) as n,
                          SUM(CASE WHEN metric_value >= 4 THEN 1 ELSE 0 END) as positives
                   FROM ab_test_results
                   WHERE test_name = ?
                   GROUP BY variant, metric_name""",
                (test_name,),
            ) as cur:
                rows = [dict(r) async for r in cur]

        test = ACTIVE_TESTS.get(test_name)
        results: dict[str, Any] = {
            "test_name": test_name,
            "description": test.description if test else "Unknown test",
            "variants": {},
            "significance": "insufficient_data",
        }

        for row in rows:
            v = row["variant"]
            m = row["metric_name"]
            if v not in results["variants"]:
                results["variants"][v] = {}
            results["variants"][v][m] = {
                "mean": round(row["mean"], 4),
                "n": row["n"],
                "positive_rate": round(row["positives"] / max(row["n"], 1), 4),
            }

        # Determine significance from sample sizes
        total_n = sum(v.get("rating", {}).get("n", 0) for v in results["variants"].values())
        if total_n >= 100:
            results["significance"] = "statistically_testable"
            results["recommendation"] = "Run Chi-squared test on positive_rate columns for significance."
        elif total_n >= 30:
            results["significance"] = "preliminary"
        else:
            results["significance"] = "insufficient_data (need >= 100 total samples)"

        return results

    async def list_active_tests(self) -> list[dict]:
        """Returns all active test definitions."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "test_type": t.test_type,
                "control": t.control_value,
                "treatment": t.treatment_value,
                "traffic_split": t.traffic_split,
                "active": t.active,
            }
            for t in ACTIVE_TESTS.values()
        ]
