from typing import Any

from pydantic import BaseModel, Field


class IngestTextRequest(BaseModel):
    """Request for direct text ingestion."""

    content: str = Field(..., min_length=1, description="The raw text content to index")
    source: str = Field(..., description="A unique identifier for the source (e.g., 'meeting_notes.txt')")
    author: str | None = Field(None, description="The creator of the document")


class QueryAPIRequest(BaseModel):
    """Request for a RAG query."""

    query_text: str = Field(..., min_length=2, description="The question you want to ask DeepVault")
    top_k: int = Field(5, ge=1, le=20, description="Number of context chunks to retrieve")
    chunking_strategy: str = Field("sliding", description="Specific chunking strategy to evaluate (sliding, recursive, etc.)")
    retrieval_strategy: str = Field("vector", description="Search algorithm (vector, hybrid, etc.)")
    use_query_rewriting: bool = Field(False, description="Whether to use AI-powered query expansion/rewriting")
    user_id: str | None = Field(None, description="Optional ID of the user performing the query")
    filters: dict[str, Any] | None = Field(None, description="Metadata filters (e.g., {'author': 'HR'})")
    session_id: str | None = Field(None, description="Optional ID to track conversation history")
    model_name: str | None = Field(None, description="Specific LLM model to use for generation")
    messages: list[dict[str, str]] | None = Field(None, description="Conversation history for multi-turn chat")
