"""
Dependency Injection Container for DeepVault.

This module is the single source of truth for all singleton instances.
It acts as a lightweight service locator: callers ask for a service by
calling the appropriate async factory function, and the factory either
returns a cached instance or creates one on first call.

Lifecycle:
  - initialize_all()  — called at API startup (FastAPI lifespan)
  - shutdown_all()    — called at API shutdown
  - clear_cache()     — used in tests to reset state between runs

Thread safety:
  Concurrent requests could race during first initialization if two
  requests hit a cold cache simultaneously. We use per-key asyncio.Lock
  objects to ensure exactly-once initialization.

Adding a new dependency:
  1. Write the infrastructure class (implement the right ABC).
  2. Add a factory function here following the _get_or_create pattern.
  3. Wire it into the relevant service factory.
  4. Add teardown logic in shutdown_all() if the class has .close().
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from qdrant_client import AsyncQdrantClient

from app.config import settings
from app.core.interfaces.chunker import BaseChunker
from app.core.interfaces.reranker import BaseReranker
from app.core.interfaces.retriever import BaseRetriever
from app.core.interfaces.rewriter import BaseQueryRewriter
from app.infrastructure.cache.redis import RedisCache
from app.infrastructure.chunkers.recursive import RecursiveChunker
from app.infrastructure.chunkers.semantic import SemanticChunker
from app.infrastructure.chunkers.sliding import SlidingWindowChunker
from app.infrastructure.chunkers.structure import StructureChunker
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.llm.router import LLMRouter
from app.infrastructure.logging.structured import logger
from app.infrastructure.query.classifier import QueryClassifier
from app.infrastructure.query.decomposer import QueryDecomposer
from app.infrastructure.query.rewriter import GroqQueryRewriter
from app.infrastructure.query.router import QueryRouter
from app.infrastructure.rerankers.cross_encoder import CrossEncoderReranker
from app.infrastructure.retrievers.bm25 import BM25Retriever
from app.infrastructure.retrievers.hybrid import HybridRetriever
from app.infrastructure.retrievers.vector import VectorRetriever
from app.infrastructure.stores.feedback import FeedbackStore
from app.infrastructure.stores.qdrant import QdrantVectorStore
from app.infrastructure.stores.sqlite import SqliteDocumentStore
from app.services.ab_testing import ABTestingService
from app.services.cache_service import CacheService
from app.services.document import DocumentService
from app.services.ingestion import IngestionService
from app.services.query import QueryService

# ---------------------------------------------------------------------------
# Singleton registry
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {
    "executor": ThreadPoolExecutor(max_workers=10, thread_name_prefix="dv_worker")
}

# Per-key locks prevent double-initialization under concurrent first requests
_locks: dict[str, asyncio.Lock] = {}


def _get_lock(key: str) -> asyncio.Lock:
    """Returns (creating if needed) the asyncio.Lock for a cache key."""
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


# ---------------------------------------------------------------------------
# Infrastructure factories
# ---------------------------------------------------------------------------


async def get_executor() -> ThreadPoolExecutor:
    """Shared thread pool for CPU-bound AI tasks (embedding, chunking, reranking)."""
    return _cache["executor"]


async def get_redis_cache() -> RedisCache:
    key = "redis_cache"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = RedisCache()
    return _cache[key]


async def get_cache_service() -> CacheService:
    key = "cache_service"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = CacheService(redis_cache=await get_redis_cache())
    return _cache[key]


async def get_embedder() -> BgeEmbedder:
    key = "embedder"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = BgeEmbedder(cache_service=await get_cache_service())
    return _cache[key]


async def get_chunker(
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    **kwargs: Any,
) -> BaseChunker:
    """
    Returns a chunker for the given strategy.

    Each unique (strategy, size, overlap, **kwargs) combination gets its own
    singleton so different ingestion passes can use different chunkers without
    conflict.  For the semantic strategy the cache key also includes kwargs
    like similarity_threshold so two calls with different thresholds don't
    return the same cached chunker.
    """
    effective_strategy = strategy or settings.CHUNKER_STRATEGY
    effective_size = chunk_size or settings.CHUNKER_SIZE
    effective_overlap = chunk_overlap or settings.CHUNKER_OVERLAP

    # Include strategy-specific kwargs in the cache key to prevent collisions
    # (e.g. two semantic chunkers with different similarity_threshold values)
    kwargs_suffix = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items())) if kwargs else ""
    key = f"chunker_{effective_strategy}_{effective_size}_{effective_overlap}_{kwargs_suffix}"

    async with _get_lock(key):
        if key not in _cache:
            if effective_strategy == "recursive":
                _cache[key] = RecursiveChunker(
                    chunk_size=effective_size,
                    chunk_overlap=effective_overlap,
                )
            elif effective_strategy == "semantic":
                _cache[key] = SemanticChunker(
                    embedder=await get_embedder(),
                    similarity_threshold=kwargs.get("similarity_threshold", settings.SEMANTIC_SIMILARITY_THRESHOLD),
                    min_chunk_size=kwargs.get("min_chunk_size", 100),
                    max_chunk_size=kwargs.get("max_chunk_size", 1500),
                )
            elif effective_strategy == "structure":
                _cache[key] = StructureChunker(
                    max_section_size=1500,
                    fallback_chunk_size=effective_size,
                    fallback_overlap=effective_overlap,
                )
            else:  # "sliding" or unknown → fallback to sliding
                _cache[key] = SlidingWindowChunker(
                    chunk_size=effective_size,
                    chunk_overlap=effective_overlap,
                )
            # Tag the chunker so IngestionService can record the strategy
            # in metadata without needing to know which class was chosen.
            _cache[key].strategy_name = effective_strategy

    return _cache[key]


async def get_doc_store() -> SqliteDocumentStore:
    key = "doc_store"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = SqliteDocumentStore(settings.SQLITE_DB_PATH)
    return _cache[key]


async def get_feedback_store() -> FeedbackStore:
    """
    Singleton FeedbackStore.

    FeedbackStore opens a SQLite connection on every operation, so it is
    cheap to reuse the same instance. Keeping it as a singleton avoids
    re-running table-creation migrations on every HTTP request.
    """
    key = "feedback_store"
    async with _get_lock(key):
        if key not in _cache:
            store = FeedbackStore()
            await store.initialize()
            _cache[key] = store
    return _cache[key]


async def get_ab_testing_service() -> ABTestingService:
    """
    Singleton ABTestingService.

    Same rationale as FeedbackStore — avoids re-running CREATE TABLE
    migrations on every HTTP request.
    """
    key = "ab_testing_service"
    async with _get_lock(key):
        if key not in _cache:
            service = ABTestingService()
            await service.initialize()
            _cache[key] = service
    return _cache[key]


async def get_qdrant_client() -> AsyncQdrantClient:
    """
    Shared Qdrant connection pool.

    Qdrant's AsyncQdrantClient manages connection pooling internally, so a
    single instance shared across all requests is both safe and efficient.
    The local fallback (QDRANT_HOST == "local") uses an on-disk store at
    qdrant_storage/ without requiring Docker.
    """
    key = "qdrant_client"
    async with _get_lock(key):
        if key not in _cache:
            if settings.QDRANT_HOST and settings.QDRANT_HOST != "local":
                url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
                _cache[key] = AsyncQdrantClient(url=url)
            else:
                _cache[key] = AsyncQdrantClient(path="qdrant_storage")

    # Safety guard: detect if the cached client was closed externally
    client: AsyncQdrantClient = _cache[key]
    try:
        if hasattr(client, "_client") and hasattr(client._client, "is_closed") and client._client.is_closed:
            logger.warning("Detected closed Qdrant client in cache — re-initializing.")
            del _cache[key]
            return await get_qdrant_client()
    except Exception:
        pass

    return client


async def get_vector_store(strategy: str | None = None) -> QdrantVectorStore:
    """
    Returns the Qdrant vector store for a given chunking strategy.

    Each strategy (fixed, sliding, structure, semantic) has its own isolated
    Qdrant collection (deepvault_{strategy}) so benchmark runs across
    strategies don't contaminate each other's results.

    JIT initialization: the collection is created if it doesn't exist yet.
    This adds ~10ms on the very first call per strategy.
    """
    effective_strategy = strategy or settings.CHUNKER_STRATEGY
    collection = f"deepvault_{effective_strategy}"
    key = f"vstore_{collection}"

    async with _get_lock(key):
        if key not in _cache:
            client = await get_qdrant_client()
            embedder = await get_embedder()
            vstore = QdrantVectorStore(collection_name=collection, client=client)
            await vstore.initialize(vector_size=embedder.get_dimension())
            _cache[key] = vstore

    return _cache[key]


async def get_llm_client() -> GroqLLMClient:
    key = "llm_client"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = GroqLLMClient()
    return _cache[key]


async def get_bm25_retriever() -> BM25Retriever:
    key = "bm25_retriever"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = BM25Retriever(qdrant_client=await get_qdrant_client())
    return _cache[key]


async def get_retriever(strategy: str | None = None) -> BaseRetriever:
    """
    Returns the retrieval engine for the given strategy.

    Strategy resolution:
      - "vector"         → pure Qdrant cosine similarity search
      - "bm25"           → pure BM25 keyword search (rank-bm25)
      - "hybrid"         → BM25 + Vector merged with Reciprocal Rank Fusion
      - "hybrid_rerank"  → hybrid + Cross-Encoder reranking
    """
    effective_strategy = strategy or settings.RETRIEVAL_STRATEGY

    if effective_strategy in ("hybrid", "hybrid_rerank"):
        key = "hybrid_retriever"
        async with _get_lock(key):
            if key not in _cache:
                v_retriever = VectorRetriever(embedder=await get_embedder(), vector_store=await get_vector_store())
                b_retriever = await get_bm25_retriever()
                _cache[key] = HybridRetriever(vector_retriever=v_retriever, bm25_retriever=b_retriever)
        return _cache[key]

    if effective_strategy == "bm25":
        return await get_bm25_retriever()

    # Default: vector-only
    key = "vector_retriever"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = VectorRetriever(embedder=await get_embedder(), vector_store=await get_vector_store())
    return _cache[key]


async def get_reranker() -> BaseReranker:
    key = "reranker"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = CrossEncoderReranker()
    return _cache[key]


async def get_query_rewriter() -> BaseQueryRewriter:
    key = "query_rewriter"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = GroqQueryRewriter(llm_client=await get_llm_client())
    return _cache[key]


async def get_query_router() -> QueryRouter:
    key = "query_router"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = QueryRouter(classifier=QueryClassifier())
    return _cache[key]


async def get_query_decomposer() -> QueryDecomposer:
    key = "query_decomposer"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = QueryDecomposer(llm_client=await get_llm_client())
    return _cache[key]


async def get_llm_router() -> LLMRouter:
    key = "llm_router"
    async with _get_lock(key):
        if key not in _cache:
            _cache[key] = LLMRouter()
    return _cache[key]


# ---------------------------------------------------------------------------
# Service factories
# These are what route handlers call via FastAPI's Depends() system.
# ---------------------------------------------------------------------------


async def get_ingestion_service(
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    **kwargs: Any,
) -> IngestionService:
    """
    Returns an IngestionService wired to the given chunking strategy.

    NOTE: IngestionService is NOT cached — it is lightweight and the
    strategy parameters can differ per request.
    """
    return IngestionService(
        chunker=await get_chunker(
            strategy=strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs
        ),
        embedder=await get_embedder(),
        doc_store=await get_doc_store(),
        vector_store=await get_vector_store(strategy=strategy),
    )


async def get_query_service() -> QueryService:
    """
    Returns the main RAG query service, pre-wired with all optional components.

    The reranker is only loaded into memory when the retrieval strategy
    actually requires it — saves ~100MB RAM for vector-only deployments.
    """
    reranker = None
    if settings.RETRIEVAL_STRATEGY in ("hybrid_rerank", "auto"):
        reranker = await get_reranker()

    return QueryService(
        retriever=await get_retriever(),
        llm_client=await get_llm_client(),
        cache_service=await get_cache_service(),
        reranker=reranker,
        rewriter=await get_query_rewriter(),
        router=await get_query_router(),
        decomposer=await get_query_decomposer(),
        llm_router=await get_llm_router(),
        ab_testing_service=await get_ab_testing_service(),
    )


async def get_document_service() -> DocumentService:
    return DocumentService(doc_store=await get_doc_store(), vector_store=await get_vector_store())


# ---------------------------------------------------------------------------
# Lifecycle management
# ---------------------------------------------------------------------------


async def initialize_all() -> None:
    """
    Warm up all core infrastructure connections at API startup.

    Called by the FastAPI lifespan handler. Pre-warming avoids cold-start
    latency on the first real request.
    """
    logger.info("Initializing DeepVault core infrastructure...")

    doc_store = await get_doc_store()
    redis_cache = await get_redis_cache()

    await doc_store.initialize()
    await redis_cache.initialize()

    await get_qdrant_client()
    await get_vector_store()    # Create default strategy collection if missing

    logger.info("DeepVault core ready.")


async def shutdown_all() -> None:
    """Gracefully close all persistent connections at API shutdown."""
    logger.info("Shutting down DeepVault dependencies...")

    if "qdrant_client" in _cache:
        await _cache["qdrant_client"].close()
        del _cache["qdrant_client"]
        logger.info("Qdrant connection pool closed.")

    if "doc_store" in _cache:
        await _cache["doc_store"].close()
    if "redis_cache" in _cache:
        await _cache["redis_cache"].close()

    if "executor" in _cache:
        _cache["executor"].shutdown(wait=False)
        logger.info("Thread pool released.")

    clear_cache()
    logger.info("Shutdown complete.")


def clear_cache() -> None:
    """
    Resets the singleton cache.

    Preserves long-lived infrastructure connections (executor, qdrant_client,
    doc_store, redis_cache, cache_service, embedder) to avoid connection churn
    and thread leakage when running multiple ingestion passes in sequence.
    """
    # Keys that represent live connections or heavy resources we don't want
    # to recreate on every pass.  Everything else (chunkers, vector stores,
    # services, retrievers) gets evicted so the next factory call builds
    # fresh instances with the new strategy parameters.
    PRESERVE_KEYS = {"executor", "qdrant_client", "doc_store", "redis_cache", "cache_service", "embedder"}

    preserved = {k: _cache[k] for k in PRESERVE_KEYS if k in _cache}
    _cache.clear()
    _locks.clear()
    _cache.update(preserved)
    logger.info("Dependency cache cleared.", extra={"extra_fields": {"preserved": list(preserved.keys())}})
