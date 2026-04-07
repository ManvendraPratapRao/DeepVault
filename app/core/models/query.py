from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.core.models.document import Chunk

class QueryRequest(BaseModel):
    """What the user sends us."""
    query_text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    """What we send back to the user."""
    answer: str
    sources: List[Chunk]
    latency_ms: float
    # We embed the original request metadata here for audit trails
    request_id: str
