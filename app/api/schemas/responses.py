from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SourceChunk(BaseModel):
    """A safe subset of a Chunk used for citations in the API."""
    content: str
    document_id: str
    chunk_index: int
    metadata: Dict[str, Any]

class IngestResponse(BaseModel):
    """Response returned after successful ingestion."""
    document_id: str
    source: str
    chunks_created: int
    already_existed: bool = False
    message: str

class QueryAPIResponse(BaseModel):
    """The main RAG response."""
    answer: str = Field(..., description="The AI-generated answer")
    sources: List[SourceChunk] = Field(..., description="The pieces of context used to generate the answer")
    latency_ms: float = Field(..., description="Time taken to process the query in milliseconds")
    request_id: str = Field(..., description="The unique trace ID for this request")

class HealthResponse(BaseModel):
    """System health status."""
    status: str
    version: str
    uptime_seconds: float
    components: Dict[str, str]

class DocumentSummary(BaseModel):
    """A high-level summary of a document for listing."""
    id: str
    source: str
    author: Optional[str]
    created_at: str
    version: int

class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: List[DocumentSummary]
    total: int
    limit: int
    offset: int
