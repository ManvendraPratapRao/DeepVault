# Streaming Responses Guide — Server-Sent Events (SSE)

**Phase:** 4 (Production Hardening)  
**Status:** Planned — Implementation Pending (Session 19)

---

## Overview

DeepVault's `GroqLLMClient` already implements streaming at the SDK level. This guide documents the plan to expose a streaming endpoint via **Server-Sent Events (SSE)** that allows the Streamlit UI (and any HTTP client) to receive tokens incrementally as the LLM generates them.

Without streaming, the user waits 1.5–4 seconds for the full response. With streaming, the first token appears in ~200ms and the answer is rendered progressively — identical to how ChatGPT and Claude feel.

---

## Architecture

```
Client (curl / Streamlit)
    ↓  GET /api/v1/stream?query=...
FastAPI SSE Endpoint
    ↓  QueryService.ask_stream()  [not yet implemented]
    ↓  GroqLLMClient.stream()    [already implemented]
    ↓  yield token chunks
    ↑  text/event-stream response
Client displays tokens as they arrive
```

---

## Current State

The `GroqLLMClient` in `app/infrastructure/llm/groq.py` already has the streaming hook via the Groq SDK:

```python
# Already available in the Groq SDK
stream = await client.chat.completions.create(
    model=self.model,
    messages=messages,
    stream=True   # Enables streaming
)
async for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        yield delta
```

What's **not yet built:**
- A `stream()` method on `BaseLLMClient` and `GroqLLMClient` ABCs.
- A `POST /api/v1/stream` FastAPI route with SSE response.
- Streamlit UI integration using `st.write_stream()`.

---

## Planned Implementation (Session 19)

### 1. Add `stream()` to BaseLLMClient

```python
# app/core/interfaces/llm_client.py
@abstractmethod
async def stream(
    self,
    prompt: str,
    system_prompt: str = "",
) -> AsyncGenerator[str, None]:
    """Stream tokens from the LLM as an async generator."""
    ...
```

### 2. Implement in GroqLLMClient

```python
# app/infrastructure/llm/groq.py
async def stream(self, prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
    messages = [
        {"role": "system", "content": system_prompt or self.default_system_prompt},
        {"role": "user", "content": prompt},
    ]
    stream = await self.client.chat.completions.create(
        model=self.model_name,
        messages=messages,
        stream=True,
        max_tokens=self.max_tokens,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

### 3. Create SSE Route

```python
# app/api/v1/routes/stream.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    query_service: QueryService = Depends(get_query_service),
):
    async def event_generator():
        async for token in query_service.ask_stream(request):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )
```

### 4. Streamlit Integration

```python
# app/ui/pages/chat.py
import httpx
import streamlit as st

with st.chat_message("assistant"):
    response_placeholder = st.empty()
    full_response = ""

    with httpx.stream("POST", f"{API_URL}/api/v1/stream", json=payload) as r:
        for line in r.iter_lines():
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                token = line[6:]  # Strip "data: " prefix
                full_response += token
                response_placeholder.markdown(full_response + "▌")

    response_placeholder.markdown(full_response)
```

---

## Testing with curl

Once implemented:

```bash
curl -X POST "http://localhost:8000/api/v1/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{"query_text": "What is Retrieval-Augmented Generation?", "top_k": 5}' \
  --no-buffer
```

Expected output:
```
data: Retrieval
data: -Aug
data: mented
data: Generation
data:  (RAG)
data:  is a technique...
data: [DONE]
```

---

## Important Considerations

- **Cache incompatibility:** Streaming responses cannot be cached in Redis (the full response is not available until the stream ends). The streaming endpoint should bypass the query cache or cache the full response after stream completion in a background task.
- **Reranking with streaming:** Cross-encoder reranking runs before the stream starts. The user sees the reranking delay, then streaming begins. p50 latency to first token will be higher for `hybrid_rerank` than `vector`.
- **Token counting:** Token counts are not available mid-stream from Groq. Track estimated token count from the final `usage` field sent in the last chunk with `stream_options={"include_usage": True}`.
