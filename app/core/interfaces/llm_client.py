from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class BaseLLMClient(ABC):
    """
    Interface for LLM interaction.
    Strictly handles text generation and token management.
    """

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate a complete response."""
        pass

    @abstractmethod
    async def stream(self, prompt: str, system_prompt: str | None = None) -> AsyncGenerator[str]:
        """Stream a response token by token."""
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens locally to manage context window and costs."""
        pass
