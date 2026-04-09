import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from qdrant_client import AsyncQdrantClient

from app.config import settings
from app.infrastructure.cache.redis import RedisCache
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
from app.services.cache_service import CacheService
from app.services.document import DocumentService

# Service Imports
from app.services.ingestion import IngestionService
from app.services.query import QueryService

# Global cache for singletons (The "Registry")
_cache: dict[str, Any] = {
    "executor": ThreadPoolExecutor(max_workers=4, thread_name_prefix="dv_worker")
}

async def get_executor() -> ThreadPoolExecutor:
    """Returns the shared thread pool for CPU-bound AI tasks."""
    return _cache["executor"]


async def get_redis_cache() -> RedisCache:
    if "redis_cache" not in _cache:
        _cache["redis_cache"] = RedisCache()
    return _cache["redis_cache"]


async def get_cache_service() -> CacheService:
    if "cache_service" not in _cache:
        _cache["cache_service"] = CacheService(redis_cache=await get_redis_cache())
    return _cache["cache_service"]


async def get_embedder() -> BgeEmbedder:
    if "embedder" not in _cache:
        _cache["embedder"] = BgeEmbedder(cache_service=await get_cache_service())
    return _cache["embedder"]


async def get_chunker():
    if "chunker" not in _cache:
        strategy = settings.CHUNKER_STRATEGY
        if strategy == "sliding":
            _cache["chunker"] = SlidingWindowChunker(
                window_size=settings.CHUNKER_SIZE, stride=400
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

        # Normalize the strategy name for consistent metadata tracking
        _cache["chunker"].strategy_name = strategy

    return _cache["chunker"]


async def get_doc_store() -> SqliteDocumentStore:
    if "doc_store" not in _cache:
        _cache["doc_store"] = SqliteDocumentStore(settings.SQLITE_DB_PATH)
    return _cache["doc_store"]


async def get_qdrant_client() -> AsyncQdrantClient:
    """Singleton for the shared Qdrant connection pool."""
    if "qdrant_client" not in _cache:
        if settings.QDRANT_HOST and settings.QDRANT_HOST != "local":
            url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
            _cache["qdrant_client"] = AsyncQdrantClient(url=url)
        else:
            _cache["qdrant_client"] = AsyncQdrantClient(path="qdrant_storage")
    return _cache["qdrant_client"]


async def get_vector_store(strategy: str | None = None) -> QdrantVectorStore:
    """
    Factory for Qdrant storage.
    Supports JIT (Just-In-Time) initialization of strategy-specific collections.
    """
    # 1. Determine the exact collection namespace
    effective_strategy = strategy or settings.CHUNKER_STRATEGY
    collection = f"deepvault_{effective_strategy}"
    cache_key = f"vstore_{collection}"
    
    if cache_key not in _cache:
        client = await get_qdrant_client()
        embedder = await get_embedder()
        
        # 2. Instantiate the store with the shared client
        vstore = QdrantVectorStore(collection_name=collection, client=client)
        
        # 3. JIT Initialization (Ensures the collection exists with right dims)
        # This only adds ~10ms overhead after the first call per strategy
        await vstore.initialize(vector_size=embedder.get_dimension())
        
        _cache[cache_key] = vstore
        
    return _cache[cache_key]


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
    return QueryService(
        retriever=await get_retriever(),
        llm_client=await get_llm_client(),
        cache_service=await get_cache_service(),
    )


async def get_document_service() -> DocumentService:
    return DocumentService(doc_store=await get_doc_store(), vector_store=await get_vector_store())


# --- LIFECYCLE MANAGEMENT ---


async def initialize_all():
    """Starts up core infrastructure connections (Called at API start)."""
    logger.info("Initializing DeepVault core backbone...")

    # 1. Warm up core infrastructure (Synchronous dependencies)
    doc_store = await get_doc_store()
    redis_cache = await get_redis_cache()
    
    await doc_store.initialize()
    await redis_cache.initialize()

    # 2. Warm up the shared Qdrant connection pool
    await get_qdrant_client()

    # 3. Warm up the default strategy
    await get_vector_store()

    logger.info("DeepVault core ready. Background workers initialized.")


async def shutdown_all():
    """Safely closes all database connections (Called at API stop)."""
    logger.info("Shutting down DeepVault dependencies...")
    
    if "qdrant_client" in _cache:
        await _cache["qdrant_client"].close()
        logger.info("Closed Qdrant connection pool.")
        
    if "doc_store" in _cache:
        await _cache["doc_store"].close()
    if "redis_cache" in _cache:
        await _cache["redis_cache"].close()

    if "executor" in _cache:
        _cache["executor"].shutdown(wait=False)
        logger.info("Compute workers released.")
        
    clear_cache()
    logger.info("Shutdown complete.")


def clear_cache():
    """Manually resets singleton cache - useful for multi-pass seating/testing."""
    # Note: We preserve the executor to avoid thread-leakage during reloads
    temp_executor = _cache.get("executor")
    _cache.clear()
    if temp_executor:
        _cache["executor"] = temp_executor
    logger.info("Dependency cache cleared.")
