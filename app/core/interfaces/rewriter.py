from abc import ABC, abstractmethod


class BaseQueryRewriter(ABC):
    """
    Interface for query rewriting and expansion logic.
    Used to transform user queries into more descriptive or search-optimized terms.
    """

    @abstractmethod
    async def rewrite(self, query: str) -> str:
        """
        Rewrite the input query into an expanded or more descriptive version.

        Args:
            query: The raw user query.

        Returns:
            The rewritten/expanded query string.
        """
        pass
