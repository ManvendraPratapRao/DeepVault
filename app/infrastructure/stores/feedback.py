"""
FeedbackStore — SQLite-backed storage for user feedback on RAG responses.

Phase 5 / Session 26 feature.

Schema:
    feedback (
        id          TEXT PRIMARY KEY,
        request_id  TEXT NOT NULL,
        query_text  TEXT NOT NULL,
        answer_text TEXT NOT NULL,
        rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment     TEXT,
        retrieval_strategy TEXT,
        chunking_strategy  TEXT,
        session_id  TEXT,
        created_at  TEXT NOT NULL
    )
"""

import uuid
from typing import Any

import aiosqlite

from app.infrastructure.logging.structured import logger

_DEFAULT_DB = "deepvault.db"


class FeedbackStore:
    """Async SQLite store for user feedback on RAG responses."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path

    async def initialize(self) -> None:
        """Ensures the feedback table exists."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id                 TEXT PRIMARY KEY,
                    request_id         TEXT NOT NULL,
                    query_text         TEXT NOT NULL,
                    answer_text        TEXT NOT NULL,
                    rating             INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                    comment            TEXT,
                    retrieval_strategy TEXT,
                    chunking_strategy  TEXT,
                    session_id         TEXT,
                    created_at         TEXT NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_feedback_strategy ON feedback(retrieval_strategy)")
            await db.commit()
        logger.info("FeedbackStore initialized.")

    async def save_feedback(
        self,
        request_id: str,
        query_text: str,
        answer_text: str,
        rating: int,
        comment: str | None,
        retrieval_strategy: str | None,
        chunking_strategy: str | None,
        session_id: str | None,
        created_at: str,
    ) -> str:
        """Saves one feedback record. Returns the generated feedback ID."""
        feedback_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO feedback
                   (id, request_id, query_text, answer_text, rating, comment,
                    retrieval_strategy, chunking_strategy, session_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feedback_id, request_id, query_text, answer_text, rating,
                    comment, retrieval_strategy, chunking_strategy, session_id, created_at,
                ),
            )
            await db.commit()

        return feedback_id

    async def get_analytics(self) -> dict[str, Any]:
        """Returns aggregated analytics for the Streamlit feedback dashboard."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Overall average rating
            async with db.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as total FROM feedback") as cur:
                row = await cur.fetchone()
                overall_avg = round(row["avg_rating"] or 0.0, 2)
                total_count = row["total"]

            # Rating distribution (1-5 histogram)
            distribution: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            async with db.execute("SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating") as cur:
                async for row in cur:
                    distribution[row["rating"]] = row["cnt"]

            # Average rating by retrieval strategy
            strategy_ratings: dict[str, dict] = {}
            async with db.execute(
                """SELECT retrieval_strategy,
                          AVG(rating) as avg_rating,
                          COUNT(*) as total
                   FROM feedback
                   WHERE retrieval_strategy IS NOT NULL
                   GROUP BY retrieval_strategy
                   ORDER BY avg_rating DESC"""
            ) as cur:
                async for row in cur:
                    strategy_ratings[row["retrieval_strategy"]] = {
                        "avg_rating": round(row["avg_rating"], 2),
                        "total_responses": row["total"],
                    }

            # Recent low-rated responses (rating <= 2) for quality review
            low_rated = []
            async with db.execute(
                """SELECT id, query_text, rating, comment, retrieval_strategy, created_at
                   FROM feedback WHERE rating <= 2
                   ORDER BY created_at DESC LIMIT 20"""
            ) as cur:
                async for row in cur:
                    low_rated.append(dict(row))

        return {
            "overall": {"average_rating": overall_avg, "total_feedback": total_count},
            "rating_distribution": distribution,
            "by_retrieval_strategy": strategy_ratings,
            "recent_low_ratings": low_rated,
        }

    async def get_recent(self, limit: int = 50) -> list[dict]:
        """Returns the most recent feedback entries for display."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
