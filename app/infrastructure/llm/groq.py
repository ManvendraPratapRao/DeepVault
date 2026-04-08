from collections.abc import AsyncGenerator

import groq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.interfaces.llm_client import BaseLLMClient
from app.infrastructure.logging.structured import logger


class GroqLLMClient(BaseLLMClient):
    """
    Implementation of the BaseLLMClient using the Groq SDK.
    Optimized for low-latency Llama-3 inference with automatic retry on transient failures.
    """

    def __init__(self):
        if not settings.GROQ_API_KEY:
            logger.error("GROQ_API_KEY is missing from environment settings.")
            raise ValueError("GROQ_API_KEY must be set in .env")

        self.client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL_NAME

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Groq API call failed, retrying (attempt {retry_state.attempt_number}/3)...",
            extra={"extra_fields": {"error": str(retry_state.outcome.exception())}},
        ),
    )
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Sends a single completion request to Groq with automatic retry."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return completion.choices[0].message.content
        except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError):
            raise  # Let tenacity handle these
        except Exception as e:
            logger.error(f"Groq API Error: {str(e)}", extra={"extra_fields": {"model": self.model}})
            raise

    async def stream(self, prompt: str, system_prompt: str | None = None) -> AsyncGenerator[str]:
        """Streams the response token-by-token for the UI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Groq Streaming Error: {str(e)}")
            raise

    async def count_tokens(self, text: str) -> int:
        """
        Approximate token count for the current model.
        Groq doesn't provide a direct API for this, so we use a standard
        heuristic (chars / 4) or can integrate a library like tiktoken later.
        """
        # Heuristic for Llama-3 (Better than nothing)
        return len(text) // 4
