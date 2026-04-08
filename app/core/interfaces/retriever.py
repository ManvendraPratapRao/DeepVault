from abc import ABC, abstractmethod

from app.core.models.document import Chunk


class BaseRetriever(ABC):
    """
    Interface for finding relevant document chunks.
    This will eventually coordinate between Vector, BM25, and Graph stores.
    """

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[Chunk]:
        """Find the top-k most relevant chunks based on a query."""
        pass
