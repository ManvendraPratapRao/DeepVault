from typing import Any

from pydantic import BaseModel

from app.core.models.document import Chunk


class QueryRequest(BaseModel):
    """What the user sends us."""

    query_text: str
    user_id: str | None = None
    session_id: str | None = None
    filters: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    """What we send back to the user."""

    answer: str
    sources: list[Chunk]
    latency_ms: float
    # We embed the original request metadata here for audit trails
    request_id: str
