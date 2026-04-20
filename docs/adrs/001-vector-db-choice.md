# ADR-001: Vector Database — Qdrant

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Manvendra Pratap Rao

---

## Context

DeepVault requires a vector database to store and query 384-dimensional embeddings produced by `BAAI/bge-small-en-v1.5`. The system must support:

- Sub-100ms nearest-neighbour search over tens of thousands of chunks.
- Metadata filtering (e.g., filter by `chunking_strategy`, `document_id`).
- Multiple isolated collections, one per chunking strategy, for side-by-side benchmarking.
- Local development mode (no Docker or external service required).
- A well-maintained Python client with async support.

The three primary candidates evaluated were **Qdrant**, **FAISS**, and **ChromaDB**.

---

## Decision

**Use Qdrant** as the vector store for all phases of DeepVault.

---

## Evaluation

### Qdrant

| Criterion | Assessment |
|-----------|------------|
| Metadata filtering | ✅ First-class. Payload-based filters with `must`, `should` conditions. |
| Multiple collections | ✅ Native concept. Each chunking strategy gets its own collection. |
| Local mode | ✅ `AsyncQdrantClient(path="qdrant_storage")` — zero setup. |
| Docker mode | ✅ Official Docker image, used in `docker-compose.yml`. |
| Async Python client | ✅ `qdrant-client[async]` is the default. |
| HNSW algorithm | ✅ Production-grade approximate nearest neighbours. |
| Scroll/pagination | ✅ Required for BM25 index bootstrap (Phase 2). |
| REST + gRPC | ✅ Both supported; REST used for compatibility. |

### FAISS (Facebook AI Similarity Search)

| Criterion | Assessment |
|-----------|------------|
| Metadata filtering | ❌ Not supported natively. Requires a separate metadata store and post-filtering. |
| Multiple collections | ⚠️ Requires separate index files per collection — no unified client. |
| Local mode | ✅ Pure in-process, no server. |
| Async Python client | ❌ Synchronous only. Requires `asyncio.to_thread` for every call. |
| Production use | ⚠️ Research-grade. Requires custom index serialization. |

**Rejected:** Metadata filtering is essential for retrieving strategy-specific chunks. FAISS's lack of native filtering would require maintaining a parallel SQLite index, increasing complexity.

### ChromaDB

| Criterion | Assessment |
|-----------|------------|
| Metadata filtering | ✅ Supported via `where` clauses. |
| Multiple collections | ✅ Supported. |
| Local mode | ✅ File-based persistence. |
| Async Python client | ⚠️ Limited async support in early stable versions. |
| Production readiness | ⚠️ Primarily designed for prototyping. The server mode is less battle-tested than Qdrant. |
| Scroll/pagination | ⚠️ Scroll API less mature; BM25 bootstrap (Phase 2) would be slower. |

**Rejected:** ChromaDB is excellent for rapid prototyping but lacks the production robustness and async-first client that Qdrant provides. Qdrant's scroll API was specifically needed for the BM25 retriever's index bootstrapping in Phase 2.

---

## Consequences

**Positive:**
- Metadata filtering enables per-strategy queries without maintaining separate indices.
- Scroll API allows the BM25 retriever to load all chunks into memory for indexing.
- Local and Docker modes allow development without external services.
- The `AsyncQdrantClient` integrates naturally with FastAPI's async event loop.

**Negative:**
- Adds a runtime dependency (Docker in production, local storage in development).
- Vector dimensions are fixed at collection creation — re-indexing required if the embedder changes.
- Not as lightweight as FAISS for pure similarity search without filtering.

---

## Implementation Notes

- Collection naming convention: `deepvault_{strategy}` (e.g., `deepvault_fixed`, `deepvault_sliding`).
- Collections are created with JIT initialization in `QdrantVectorStore.initialize()`.
- The Qdrant client is a singleton, managed by the `app/dependencies.py` module.
- Local storage path: `qdrant_storage/` in the project root (`.gitignore`d).
