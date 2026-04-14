from abc import ABC, abstractmethod

from app.core.models.document import Chunk


class BaseReranker(ABC):
    """
    Interface for Re-Ranking engines. 
    Accepts an initial list of chunks, scores them against the query, and trims the list.
    """

    @abstractmethod
    async def rerank(self, query: str, chunks: list[Chunk], top_k: int = 5) -> list[Chunk]:
        """Rescore and slice the top-K chunks contextually."""
        pass
