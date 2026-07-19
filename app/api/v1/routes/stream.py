"""
SSE Streaming endpoint for DeepVault.

POST /api/v1/stream

Returns a Server-Sent Events (text/event-stream) response that yields
LLM tokens as they are produced.  The client can display them progressively,
giving a ChatGPT-like feel.

SSE format used:
    data: <token>\n\n          – one token per event
    data: [DONE]\n\n           – sentinel: stream finished successfully
    data: [ERROR] <msg>\n\n     – sentinel: unrecoverable error mid-stream
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.requests import QueryAPIRequest
from app.core.models.query import QueryRequest
from app.dependencies import get_query_service
from app.services.query import QueryService

from app.api.dependencies import rate_limit_dependency

router = APIRouter()


@router.post(
    "",
    summary="Streaming RAG Query (SSE)",
    description=(
        "Runs the full RAG pipeline (retrieve → optionally rerank → generate) "
        "and streams the LLM answer token-by-token via Server-Sent Events.  "
        "Connect with `EventSource` (JS) or `httpx` streaming (Python/curl)."
    ),
    response_description="text/event-stream — `data: <token>` per event, `data: [DONE]` at end.",
)
async def stream_query(
    request: QueryAPIRequest,
    fastapi_req: Request,
    service: QueryService = Depends(get_query_service),
    _auth: str = Depends(rate_limit_dependency),
):
    """
    Streaming variant of POST /api/v1/query.

    Usage with curl:
        curl -X POST http://localhost:8000/api/v1/stream \\
             -H "X-API-KEY: $API_KEY" \\
             -H "Content-Type: application/json" \\
             -d '{"query_text": "What is RAG?", "top_k": 5}' --no-buffer
    """
    request_id = getattr(fastapi_req.state, "request_id", "internal")

    # Map API schema → internal model (same pattern as query.py)
    service_request = QueryRequest(
        query_text=request.query_text,
        top_k=request.top_k,
        chunking_strategy=request.chunking_strategy,
        retrieval_strategy=request.retrieval_strategy,
        use_query_rewriting=request.use_query_rewriting,
        user_id=request.user_id,
        session_id=request.session_id,
        filters=request.filters,
        model_name=request.model_name,
        messages=request.messages,
    )

    async def event_generator():
        try:
            async for token in service.ask_stream(service_request, request_id=request_id):
                # Each token is a separate SSE event
                yield f"data: {token}\n\n"
            # Signal successful end of stream
            yield "data: [DONE]\n\n"
        except Exception as e:
            # Stream a structured error so the client can surface it
            yield f"data: [ERROR] {type(e).__name__}: {e}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Prevent proxy/CDN buffering — critical for SSE to work
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )
