from collections.abc import AsyncGenerator

import groq
import tiktoken
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.interfaces.llm_client import BaseLLMClient
from app.core.models.query import LLMResult, TokenUsage
from app.infrastructure.logging.structured import logger

_enc = tiktoken.get_encoding("cl100k_base")


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

    def _prepare_messages(self, prompt: str, system_prompt: str | None, history: list[dict[str, str]] | None) -> list[dict]:
        """Prepares messages ensuring strictly alternating roles for Llama-3 compatibility."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        if history:
            valid_history = []
            expected_role = "assistant"
            # Reverse iterate last 10 messages to enforce assistant -> user sequence backwards
            for msg in reversed(history[-10:]):
                if msg["role"] == expected_role:
                    valid_history.insert(0, msg)
                    expected_role = "user" if expected_role == "assistant" else "assistant"
            
            # If the first message in our valid_history is "assistant", drop it
            if valid_history and valid_history[0]["role"] == "assistant":
                valid_history.pop(0)
                
            messages.extend(valid_history)

        messages.append({"role": "user", "content": prompt})
        return messages

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Groq API call failed (Attempt {retry_state.attempt_number}/5). Retrying...",
            extra={
                "extra_fields": {
                    "error": str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
                    "model": "llama-3.1",
                }
            },
        ),
    )
    async def generate(self, prompt: str, system_prompt: str | None = None, model_name: str | None = None, history: list[dict[str, str]] | None = None) -> LLMResult:
        """Sends a single completion request to Groq with automatic retry."""

        messages = self._prepare_messages(prompt, system_prompt, history)

        try:
            effective_model = model_name or self.model
            completion = await self.client.chat.completions.create(
                model=effective_model,
                messages=messages,  # type: ignore
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )

            # Extract telemetry from Groq usage object
            groq_usage = completion.usage
            usage = TokenUsage(
                prompt_tokens=groq_usage.prompt_tokens if groq_usage else 0,
                completion_tokens=groq_usage.completion_tokens if groq_usage else 0,
                total_tokens=groq_usage.total_tokens if groq_usage else 0,
            )

            answer = completion.choices[0].message.content or ""
            return LLMResult(answer=answer, usage=usage)
        except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError):
            raise  # Let tenacity handle these
        except Exception as e:
            logger.error(f"Groq API Error: {str(e)}", extra={"extra_fields": {"model": self.model}})
            raise

    async def stream(  # type: ignore[override]
        self, prompt: str, system_prompt: str | None = None, model_name: str | None = None, history: list[dict[str, str]] | None = None
    ) -> AsyncGenerator[str]:  # noqa: E501
        """Streams the response token-by-token for the UI."""
        messages = self._prepare_messages(prompt, system_prompt, history)

        try:
            effective_model = model_name or self.model
            stream_resp = await self.client.chat.completions.create(
                model=effective_model,
                messages=messages,  # type: ignore
                temperature=settings.LLM_TEMPERATURE,
                stream=True,
            )
            async for chunk in stream_resp:  # type: ignore
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Groq Streaming Error: {str(e)}")
            raise

    async def count_tokens(self, text: str) -> int:
        """
        Token count for the current model.
        Groq doesn't provide a direct API for this, so we use tiktoken
        with cl100k_base encoding as a close approximation.
        """
        return len(_enc.encode(text))
