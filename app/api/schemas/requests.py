from typing import Any

from pydantic import BaseModel, Field


class IngestTextRequest(BaseModel):
    """Request for direct text ingestion."""

    content: str = Field(..., min_length=1, description="The raw text content to index")
    source: str = Field(
        ..., description="A unique identifier for the source (e.g., 'meeting_notes.txt')"
    )
    author: str | None = Field(None, description="The creator of the document")


class QueryAPIRequest(BaseModel):
    """Request for a RAG query."""

    query_text: str = Field(..., min_length=2, description="The question you want to ask DeepVault")
    top_k: int = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")
    filters: dict[str, Any] | None = Field(
        None, description="Metadata filters (e.g., {'author': 'HR'})"
    )
    session_id: str | None = Field(None, description="Optional ID to track conversation history")
