import sys
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.logging import LoggingMiddleware
from app.api.v1 import api_router
from app.config import settings
from app.dependencies import initialize_all, shutdown_all
from app.infrastructure.logging.structured import logger
from app.infrastructure.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler — runs startup and shutdown logic."""
    await initialize_all()
    logger.info(f"DeepVault API v{settings.VERSION} is ready.")
    yield
    await shutdown_all()
    logger.info("DeepVault API has shut down safely.")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Standardized last-resort error handler.

    Catches ALL unhandled exceptions that escape the route handlers and
    normalizes them into a clean JSON response with a correlation ID.
    Also writes to stderr as a redundant signal for ops teams monitoring
    process output directly (useful when the structured log pipeline fails).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    error_trace = traceback.format_exc()

    logger.error(
        f"CRITICAL: Unhandled {type(exc).__name__}: {str(exc)}",
        extra={"extra_fields": {"request_id": request_id, "path": request.url.path, "traceback": error_trace}},
    )

    # Emergency backup to stderr — useful when log aggregation is unavailable
    sys.stderr.write("\n" + "=" * 80 + "\n")
    sys.stderr.write(f"🔥 DEEPVAULT CRITICAL ERROR [{request_id}]\n")
    sys.stderr.write(f"Error Type: {type(exc).__name__}\n")
    sys.stderr.write(f"Message: {str(exc)}\n")
    sys.stderr.write("-" * 40 + "\n")
    sys.stderr.write(error_trace)
    sys.stderr.write("=" * 80 + "\n\n")

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Our engineers have been notified.",
            "request_id": request_id,
            "type": type(exc).__name__,
        },
    )


def create_app() -> FastAPI:
    """Factory function for the FastAPI application."""
    app = FastAPI(
        title="DeepVault Enterprise RAG",
        description=(
            "Production-grade Retrieval-Augmented Generation platform. "
            "Supports 4 chunking strategies, 6 retrieval pipelines, "
            "intelligent query routing, and token-by-token SSE streaming."
        ),
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ------------------------------------------------------------------
    # OpenTelemetry & Phoenix Tracing
    # ------------------------------------------------------------------
    setup_tracing(app)

    # ------------------------------------------------------------------
    # CORS — must be added before other middleware so it fires first.
    # Restricts cross-origin access to the configured origin allowlist.
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Request ID injection + structured access logging
    # ------------------------------------------------------------------
    app.add_middleware(LoggingMiddleware)

    # ------------------------------------------------------------------
    # API routes (versioned under /api/v1)
    # ------------------------------------------------------------------
    app.include_router(api_router, prefix="/api/v1")

    # ------------------------------------------------------------------
    # Global exception handler — last line of defense
    # ------------------------------------------------------------------
    app.add_exception_handler(Exception, global_exception_handler)  # type: ignore[arg-type]

    return app


app = create_app()
