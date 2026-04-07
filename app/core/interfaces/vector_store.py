from abc import ABC, abstractmethod
from typing import List, Optional
from app.core.models.document import Chunk

class BaseVectorStore(ABC):
    """
    Interface for vector database operations.
    Handles indexing and searching of high-dimensional vectors.
    """
    @abstractmethod
    async def upsert_chunks(self, chunks: List[Chunk]) -> None:
        """Insert or update a batch of chunks with their embeddings."""
        pass

    @abstractmethod
    async def search(
        self, 
        query_vector: List[float], 
        top_k: int = 5,
        filters: Optional[dict] = None
    ) -> List[Chunk]:
        """Perform a vector similarity search."""
        pass

    @abstractmethod
    async def delete_by_doc_id(self, doc_id: str) -> None:
        """Remove all chunks associated with a specific document."""
        pass
