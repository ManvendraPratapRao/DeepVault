"""
Feedback API — POST /api/v1/feedback

Allows users to rate RAG responses on a 1–5 scale with an optional
free-text comment. Results are stored in SQLite and exposed via the
/analytics endpoint for quality monitoring.

Why we collect feedback:
  LLM-as-judge evaluation gives us offline quality metrics, but user
  ratings are the ground truth for production quality. A persistent
  drop in average rating is the earliest signal that a retrieval or
  prompt change hurt real-world performance.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_api_key
from app.dependencies import get_feedback_store
from app.infrastructure.logging.structured import logger
from app.infrastructure.stores.feedback import FeedbackStore

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    request_id: str = Field(..., description="The request_id from the QueryResponse being rated.")
    query_text: str = Field(..., min_length=1, description="The original query text.")
    answer_text: str = Field(..., min_length=1, description="The generated answer being rated.")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (terrible) to 5 (excellent).")
    comment: str | None = Field(None, max_length=1000, description="Optional free-text feedback.")
    retrieval_strategy: str | None = Field(None, description="Retrieval strategy used (for cohort analysis).")
    chunking_strategy: str | None = Field(None, description="Chunking strategy used (for cohort analysis).")
    session_id: str | None = Field(None, description="User session ID for cohort tracking.")


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


from app.services.ab_testing import ABTestingService, get_variant_value
from app.api.dependencies import get_api_key
from app.dependencies import get_ab_testing_service, get_feedback_store

@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    store: FeedbackStore = Depends(get_feedback_store),
    ab_testing_service: ABTestingService = Depends(get_ab_testing_service),
    _auth: str = Depends(get_api_key),
) -> FeedbackResponse:
    """
    Submit user feedback for a RAG response.

    The `request_id` links the rating back to the original query trace,
    enabling per-response quality analysis in the Streamlit dashboard.
    """
    feedback_id = await store.save_feedback(
        request_id=request.request_id,
        query_text=request.query_text,
        answer_text=request.answer_text,
        rating=request.rating,
        comment=request.comment,
        retrieval_strategy=request.retrieval_strategy,
        chunking_strategy=request.chunking_strategy,
        session_id=request.session_id,
        created_at=datetime.now(UTC).isoformat(),
    )

    # Record Rating for A/B Tests (if in a session)
    if request.session_id:
        for test_name in ["prompt_v3_test", "rerank_vs_hybrid"]:
            variant = get_variant_value(request.session_id, test_name)
            if variant:
                import asyncio
                asyncio.create_task(ab_testing_service.record_result(
                    test_name=test_name,
                    variant=variant,
                    metric_name="rating",
                    metric_value=float(request.rating),
                    session_id=request.session_id,
                ))

    logger.info(
        f"Feedback submitted: id={feedback_id} rating={request.rating}",
        extra={
            "extra_fields": {
                "feedback_id": feedback_id,
                "rating": request.rating,
                "request_id": request.request_id,
            }
        },
    )

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="accepted",
        message=f"Thank you for your feedback (rating: {request.rating}/5)",
    )


@router.get("/analytics")
async def get_feedback_analytics(
    store: FeedbackStore = Depends(get_feedback_store),
    _auth: str = Depends(get_api_key),
) -> dict:
    """
    Returns aggregated feedback analytics:
    - Average rating (overall and per strategy)
    - Rating distribution histogram (1–5)
    - Recent low-rated responses for quality review
    """
    return await store.get_analytics()
