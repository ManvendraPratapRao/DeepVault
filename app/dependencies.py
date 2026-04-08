from typing import Any

from app.config import settings
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.chunkers.semantic import SemanticChunker
from app.infrastructure.chunkers.sliding import SlidingWindowChunker
from app.infrastructure.chunkers.structure import StructureChunker

# Infrastructure Imports
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.logging.structured import logger
from app.infrastructure.retrievers.vector import VectorRetriever
from app.infrastructure.stores.qdrant import QdrantVectorStore
from app.infrastructure.stores.sqlite import SqliteDocumentStore
from app.services.document import DocumentService

# Service Imports
from app.services.ingestion import IngestionService
from app.services.query import QueryService

# Global cache for singletons (The "Registry")
_cache: dict[str, Any] = {}


async def get_embedder() -> BgeEmbedder:
    if "embedder" not in _cache:
        _cache["embedder"] = BgeEmbedder()
    return _cache["embedder"]


async def get_chunker():
    if "chunker" not in _cache:
        strategy = settings.CHUNKER_STRATEGY
        if strategy == "sliding":
            _cache["chunker"] = SlidingWindowChunker(
                chunk_size=settings.CHUNKER_SIZE, chunk_overlap=settings.CHUNKER_OVERLAP
            )
        elif strategy == "semantic":
            embedder = await get_embedder()
            _cache["chunker"] = SemanticChunker(
                embedder=embedder, similarity_threshold=settings.SEMANTIC_SIMILARITY_THRESHOLD
            )
        elif strategy == "structure":
            _cache["chunker"] = StructureChunker(
                max_section_size=1500,
                fallback_chunk_size=settings.CHUNKER_SIZE,
                fallback_overlap=settings.CHUNKER_OVERLAP,
            )
        else:
            _cache["chunker"] = FixedWindowChunker(
                chunk_size=settings.CHUNKER_SIZE, chunk_overlap=settings.CHUNKER_OVERLAP
            )
    return _cache["chunker"]


async def get_doc_store() -> SqliteDocumentStore:
    if "doc_store" not in _cache:
        _cache["doc_store"] = SqliteDocumentStore(settings.SQLITE_DB_PATH)
    return _cache["doc_store"]


async def get_vector_store() -> QdrantVectorStore:
    if "vector_store" not in _cache:
        _cache["vector_store"] = QdrantVectorStore(collection_name=settings.QDRANT_COLLECTION)
    return _cache["vector_store"]


async def get_llm_client() -> GroqLLMClient:
    if "llm_client" not in _cache:
        _cache["llm_client"] = GroqLLMClient()
    return _cache["llm_client"]


async def get_retriever() -> VectorRetriever:
    if "retriever" not in _cache:
        embedder = await get_embedder()
        vstore = await get_vector_store()
        _cache["retriever"] = VectorRetriever(embedder=embedder, vector_store=vstore)
    return _cache["retriever"]


# --- SERVICE BUILDERS ---
# These are what the actual API routes will call


async def get_ingestion_service() -> IngestionService:
    return IngestionService(
        chunker=await get_chunker(),
        embedder=await get_embedder(),
        doc_store=await get_doc_store(),
        vector_store=await get_vector_store(),
    )


async def get_query_service() -> QueryService:
    return QueryService(retriever=await get_retriever(), llm_client=await get_llm_client())


async def get_document_service() -> DocumentService:
    return DocumentService(doc_store=await get_doc_store(), vector_store=await get_vector_store())


# --- LIFECYCLE MANAGEMENT ---


async def initialize_all():
    """Starts up all database connections and models (Called at API start)."""
    logger.info("Initializing all DeepVault global dependencies...")

    doc_store = await get_doc_store()
    vstore = await get_vector_store()
    embedder = await get_embedder()

    await doc_store.initialize()
    await vstore.initialize(vector_size=embedder.get_dimension())

    logger.info("DeepVault dependencies ready.")


async def shutdown_all():
    """Safely closes all database connections (Called at API stop)."""
    logger.info("Shutting down DeepVault dependencies...")
    if "doc_store" in _cache:
        await _cache["doc_store"].close()
    if "vector_store" in _cache:
        await _cache["vector_store"].close()
    _cache.clear()
    logger.info("Shutdown complete.")
