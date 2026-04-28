"""
Feedback API endpoint — POST /api/v1/feedback

Phase 5 / Session 26 feature.

Allows users to rate RAG responses (thumbs up/down + optional comment).
Results are stored in SQLite and exposed via analytics in the Streamlit UI.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.routes.query import get_api_key
from app.infrastructure.logging.structured import logger
from app.infrastructure.stores.feedback import FeedbackStore

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    request_id: str = Field(..., description="The request_id from the QueryResponse being rated")
    query_text: str = Field(..., min_length=1, description="The original query")
    answer_text: str = Field(..., min_length=1, description="The answer being rated")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (terrible) to 5 (excellent)")
    comment: str | None = Field(None, max_length=1000, description="Optional free-text feedback")
    retrieval_strategy: str | None = Field(None, description="Which retrieval strategy was used")
    chunking_strategy: str | None = Field(None, description="Which chunking strategy was used")
    session_id: str | None = Field(None, description="User session ID for cohort analysis")


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    _auth: str = Depends(get_api_key),
):
    """
    Submit user feedback for a RAG response.

    Stores rating (1-5), optional comment, and strategy metadata in SQLite.
    Use GET /api/v1/feedback/analytics to see aggregated results.
    """
    store = FeedbackStore()
    await store.initialize()

    feedback_id = await store.save_feedback(
        request_id=request.request_id,
        query_text=request.query_text,
        answer_text=request.answer_text,
        rating=request.rating,
        comment=request.comment,
        retrieval_strategy=request.retrieval_strategy,
        chunking_strategy=request.chunking_strategy,
        session_id=request.session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        f"Feedback submitted: id={feedback_id} rating={request.rating}",
        extra={"extra_fields": {"feedback_id": feedback_id, "rating": request.rating, "request_id": request.request_id}},
    )

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="accepted",
        message=f"Thank you for your feedback (rating: {request.rating}/5)",
    )


@router.get("/analytics")
async def get_feedback_analytics(_auth: str = Depends(get_api_key)):
    """
    Returns aggregated feedback analytics:
    - Average rating overall and by strategy
    - Rating distribution (1-5 histogram)
    - Recent low-rated responses (for quality review)
    """
    store = FeedbackStore()
    await store.initialize()
    return await store.get_analytics()
