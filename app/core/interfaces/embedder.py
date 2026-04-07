from abc import ABC, abstractmethod
from typing import List

class BaseEmbedder(ABC):
    """
    Interface for generating vector representations of text.
    Essential for semantic search and hybrid retrieval.
    """
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Convert a single string into a vector."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Convert a list of strings into a list of vectors efficiently."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Returns the size of the vector (e.g., 384 for bge-small)."""
        pass
