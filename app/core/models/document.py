from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4

class DocumentMetadata(BaseModel):

    """Extensible metadata for any ingested document."""

    source: str
    author: Optional[str] = "Unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    permissions: List[str] = Field(default_factory=lambda: ["admin"])
    extra: Dict[str, Any] = Field(default_factory=dict)

class Document(BaseModel):
    """The root document object."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    metadata: DocumentMetadata
    hash: str   # To detect changes and avoid re-processing

class Chunk(BaseModel):
    """A granular piece of a document used for retrieval."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    content: str
    chunk_index: int #Essential for neighbor retrieval(if ever used)
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)
    