from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware.logging import LoggingMiddleware
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

    return app


app = create_app()
