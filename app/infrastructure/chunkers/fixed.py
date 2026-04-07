import uuid
from typing import List
from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Document, Chunk

class FixedWindowChunker(BaseChunker):
    """
    Splits documents into fixed-size character chunks with optional overlap.
    Simple, fast, and very effective for most enterprise RAG use cases.
    """
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size}), "
                f"otherwise the window never advances"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> List[Chunk]:
        """
        Implementation of the fixed-window splitting logic.
        """
        chunks = []
        text = document.content
        start = 0
        index = 0

        # If the document is shorter than the chunk size, just return one chunk
        if len(text) <= self.chunk_size:
            return [
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=text,
                    chunk_index=0,
                    metadata=document.metadata.model_dump()
                )
            ]

        while start < len(text):
            # Calculate end of the window
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=index,
                    metadata=document.metadata.model_dump()
                )
            )
            
            # Move the start pointer forward, but subtract overlap to keep context
            start += (self.chunk_size - self.chunk_overlap)
            index += 1
            
        return chunks
