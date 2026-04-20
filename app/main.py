import sys
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import make_asgi_app

from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL
from app.api.v1 import api_router
from app.config import settings
from app.dependencies import initialize_all, shutdown_all
from app.infrastructure.logging.structured import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup Logic: Initialize Databases and Models
    await initialize_all()
    logger.info(f"DeepVault API v{settings.VERSION} is ready.")
    yield
    # 2. Shutdown Logic: Close connections
    await shutdown_all()
    logger.info("DeepVault API has shut down safely.")


async def global_exception_handler(request: Request, exc: Exception):
    """
    Standardized Error Normalizer.
    Catches ALL unhandled exceptions and returns a clean JSON response.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    error_trace = traceback.format_exc()

    # 1. Standard Logger (Structured JSON)
    logger.error(
        f"CRITICAL: Unhandled {type(exc).__name__}: {str(exc)}",
        extra={"extra_fields": {"request_id": request_id, "path": request.url.path, "traceback": error_trace}},
    )

    # 2. Emergency Backup: Bright Red Stderr (Senior Dev trick for ghost debugging)
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
    app = FastAPI(
        title="DeepVault Enterprise RAG",
        description="High-performance autonomous research assistant powered by Groq.",
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # Add our Request ID & Performance Logging middleware
    app.add_middleware(LoggingMiddleware)

    # Include the API router
    app.include_router(api_router, prefix="/api/v1")

    # Mount Prometheus metrics ASGI sub-application (unauthenticated, internal)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Lightweight HTTP metrics instrumentation via a plain route hook
    # (Starlette middleware wraps ALL requests including /metrics itself,
    # so we use an on-request hook here to avoid circular recording)
    @app.middleware("http")
    async def _prometheus_http_middleware(request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        # Skip the /metrics path itself to avoid self-loop
        if path != "/metrics":
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path=path, status_code=response.status_code
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)
        return response

    # Final Defense: Global Exception Handler
    app.add_exception_handler(Exception, global_exception_handler)

    return app


app = create_app()
