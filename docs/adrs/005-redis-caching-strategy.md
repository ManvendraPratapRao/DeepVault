# ADR-005: Caching Strategy — Redis for Query and Embedding Cache

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Manvendra Pratap Rao

---

## Context

DeepVault has two distinct caching needs:

**1. Query Response Cache**  
Identical or near-identical queries (e.g., FAQ-style workloads) should return cached answers without invoking the LLM. Each LLM call costs tokens and time. At p50, a query without cache takes 1.5–4 seconds end-to-end. A cache hit should take <5ms.

**2. Embedding Cache**  
Computing embeddings via `BAAI/bge-small-en-v1.5` is CPU-bound. At batch size 1 (single-query lookups), this takes ~20–60ms. For repeated queries (e.g., the same question reworded slightly), recomputing the embedding is wasteful.

Requirements:
- Sub-millisecond key lookups.
- TTL-based expiry (cached responses become stale as documents are re-ingested).
- Feature-flag controlled (can be disabled per environment or for benchmarking).
- Graceful degradation — if Redis is unavailable, the system must continue working without caching (fail-open).

Candidates: **Redis**, **Memcached**, **in-process Python dict**, **SQLite**.

---

## Decision

**Use Redis 7** for both query response caching and embedding caching, controlled by feature flags `CACHE_ENABLED` and `EMBEDDING_CACHE_ENABLED`.

---

## Evaluation

### Redis

| Criterion | Assessment |
|-----------|------------|
| Latency | ✅ Sub-millisecond round-trip latency on localhost. |
| TTL support | ✅ Native `EXPIRE`/`TTL` commands. Per-key TTL supported. |
| Async support | ✅ `redis.asyncio` client is the standard async interface. |
| Data types | ✅ String keys for hash-based lookup. JSON payloads stored as strings. |
| Docker image | ✅ Official `redis:7-alpine` image. |
| Fail-open | ✅ Implemented with `try/except` — cache miss on Redis failure, system continues. |
| Feature flags | ✅ `CACHE_ENABLED` and `EMBEDDING_CACHE_ENABLED` in `.env`. |

### Memcached

| Criterion | Assessment |
|-----------|------------|
| Latency | ✅ Similar to Redis for simple string values. |
| TTL support | ✅ Supported. |
| Data types | ⚠️ String-only. No native JSON or hash types (though not needed here). |
| Async Python client | ⚠️ Less mature async libraries than Redis. |
| Persistence | ❌ Memory-only. No persistence option. |

**Rejected:** Less ecosystem support in Python. Redis offers identical performance for this use case with a richer ecosystem.

### In-Process Python Dictionary

| Criterion | Assessment |
|-----------|------------|
| Latency | ✅ Fastest possible — in-memory. |
| TTL support | ❌ Manual implementation required. |
| Multi-process | ❌ Uvicorn spawns multiple workers; each worker has its own dict. Cache is not shared. |
| Memory limits | ❌ No eviction policy. Unbounded growth. |

**Rejected:** Does not work with multi-worker deployments.

### SQLite

| Criterion | Assessment |
|-----------|------------|
| Latency | ⚠️ Disk reads (~1–5ms). 10–100× slower than Redis. |
| TTL support | ❌ Manual — requires a background cleanup job. |

**Rejected:** Too slow for caching. Redis is the purpose-built tool here.

---

## Cache Key Design

### Query Response Cache

```
query:{sha256(query_text_utf8)}
```

- SHA-256 of the exact query string (case-sensitive, whitespace-sensitive).
- TTL: `REDIS_TTL_SECONDS` (default: 3600 seconds / 1 hour).
- Value: JSON-serialized `QueryResponse` (Pydantic model).

### Embedding Cache

```
embed:{sha256(text_utf8)}
```

- SHA-256 of the exact chunk or query text.
- TTL: same as `REDIS_TTL_SECONDS`.
- Value: JSON-serialized `list[float]` (384-dimensional embedding vector).

---

## Consequences

**Positive:**
- Cache hits reduce p50 latency from ~2s to <5ms — a 400× speedup.
- Embedding cache eliminates redundant CPU-bound model inference for repeated texts.
- TTL-based expiry ensures cache staleness is bounded.
- Feature flags allow benchmarks to bypass the cache for accurate latency measurement.
- Fail-open design means Redis downtime does not cause service outage.

**Negative:**
- Adds Redis as an infrastructure dependency (Docker in development, managed Redis in production).
- Cache invalidation on document re-ingestion is not automatic — stale responses may be returned until TTL expires.
- SHA-256 key collisions are theoretically possible but astronomically unlikely (~2^256 space).

---

## Implementation Notes

- `RedisCache` in `app/infrastructure/cache/redis.py` provides `get`, `set`, and `close` methods.
- `CacheService` in `app/services/cache_service.py` wraps `RedisCache` with business logic (key generation, serialization/deserialization).
- `BgeEmbedder` checks the embedding cache via `CacheService` before calling `model.encode()`.
- `QueryService` checks the query cache as the first step of `ask()`, before any retrieval.
- Both caches use SHA-256. MD5 was considered initially and rejected (see ADR history) in favour of the cryptographic standard.
