from typing import Any

from pydantic import BaseModel, Field

from app.core.models.document import Chunk


class TokenUsage(BaseModel):
    """Telemetry for LLM cost and context-window monitoring."""

    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)


class LLMResult(BaseModel):
    """The structured output of an LLM generation."""

    answer: str
    usage: TokenUsage = Field(default_factory=TokenUsage)


class QueryRequest(BaseModel):
    # ... (Keep existing QueryRequest)
    query_text: str
    user_id: str | None = None
    session_id: str | None = None
    strategy: str | None = None
    filters: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    """What we send back to the user."""

    answer: str
    sources: list[Chunk]
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float
    request_id: str
