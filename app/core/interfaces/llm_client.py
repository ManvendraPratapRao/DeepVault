from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

class BaseLLMClient(ABC):
    """
    Interface for LLM interaction. 
    Strictly handles text generation and token management.
    """
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a complete response."""
        pass

    @abstractmethod
    async def stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Stream a response token by token."""
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens locally to manage context window and costs."""
        pass
