from abc import ABC, abstractmethod

from app.core.models.document import Chunk


class BaseVectorStore(ABC):
    """
    Interface for vector database operations.
    Handles indexing and searching of high-dimensional vectors.
    """

    @abstractmethod
    async def upsert_chunks(self, chunks: list[Chunk]) -> None:
        """Insert or update a batch of chunks with their embeddings."""
        pass

    @abstractmethod
    async def search(
        self, query_vector: list[float], top_k: int = 5, filters: dict | None = None
    ) -> list[Chunk]:
        """Perform a vector similarity search."""
        pass

    @abstractmethod
    async def delete_by_doc_id(self, doc_id: str) -> None:
        """Remove all chunks associated with a specific document."""
        pass
