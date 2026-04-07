from fastapi import APIRouter
from .routes import health, ingest, query, documents

api_router = APIRouter()

# Register all routes with clear tags for the Swagger Documentation
api_router.include_router(health.router, prefix="/health", tags=["System"])
api_router.include_router(ingest.router, prefix="/documents", tags=["Ingestion"])
api_router.include_router(query.router, prefix="/query", tags=["Search"])
api_router.include_router(documents.router, prefix="/documents", tags=["Management"])
