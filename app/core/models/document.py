from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    """Extensible metadata for any ingested document."""

    source: str
    author: str | None = "Unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1
    permissions: list[str] = Field(default_factory=lambda: ["admin"])
    chunking_strategy: str = Field(default="fixed")
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """The root document object."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    metadata: DocumentMetadata
    hash: str  # To detect changes and avoid re-processing


class Chunk(BaseModel):
    """A granular piece of a document used for retrieval."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    content: str
    chunk_index: int  # Essential for neighbor retrieval(if ever used)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)
