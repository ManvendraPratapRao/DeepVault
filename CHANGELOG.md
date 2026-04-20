# Changelog

All notable changes to DeepVault are documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] — Phase 2 Complete

### Added
- **BM25 Keyword Retriever** (`app/infrastructure/retrievers/bm25.py`): In-process BM25Okapi index bootstrapped from Qdrant payloads via scroll API. Supports multiple isolated collections (one per chunking strategy) with lazy, double-checked-locked initialization.
- **Hybrid Retriever with RRF** (`app/infrastructure/retrievers/hybrid.py`): Merges vector and BM25 results using Reciprocal Rank Fusion (k=60, configurable per-retriever weights). Both retrievers are called in parallel via `asyncio.gather()`.
- **Cross-Encoder Reranker** (`app/infrastructure/rerankers/cross_encoder.py`): `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`. Inference offloaded with `asyncio.to_thread` for async safety. Fail-open design returns upstream results on error.
- **Query Rewriting** (`app/infrastructure/query/rewriter.py`): Optional LLM-based query expansion using Groq + v2 prompt template. Enabled per-request with `use_query_rewriting=true`.
- **4 New ABCs**: `BaseRetriever`, `BaseReranker`, `BaseQueryRewriter` in `app/core/interfaces/`. Enables clean composition.
- **`retrieval_strategy` API field**: Query endpoint now accepts `vector`, `hybrid`, or `hybrid_rerank` as the retrieval strategy per request.
- **Phase 2 Benchmark** (`docs/benchmarks/v2.0.0.md`): 135 questions × 6 retrieval strategies × 4 chunking strategies. Judge: `llama-3.3-70b-versatile`.
- **3 new ADRs**: ADR-006 (BM25), ADR-007 (RRF), ADR-008 (cross-encoder model selection).
- **Unit tests for Phase 2**: BM25 initialization, BM25 scoring, RRF merging logic, cross-encoder reranking (mocked).

### Changed
- `QueryService.ask()` now routes between `vector`, `hybrid`, and `hybrid_rerank` strategies. Fetches `top_k × 4` candidates when reranking is enabled.
- `app/dependencies.py`: Added `get_bm25_retriever()`, `get_reranker()`, `get_query_rewriter()`. `get_retriever()` factory selects the correct implementation based on `RETRIEVAL_STRATEGY` config.
- `app/config.py`: Added `RETRIEVAL_STRATEGY` setting (default: `vector`).

### Benchmark Results (Phase 2 — Fixed Chunking)
- `hybrid` retrieval: Faithfulness **3.30/5**, Hallucination **28.6%** (vs 37.5% vector-only, -8.9pp).
- `hybrid_rerank`: 100% hit rate on Sliding Window strategy.
- Best overall: **Fixed chunking + hybrid retrieval** (best faithfulness + lowest hallucination at comparable cost).

## [1.0.0] — Phase 1 Complete

### Added
- **Core RAG Pipeline**: FastAPI application with ingestion, query, and document management endpoints. Query flow: embed query → Qdrant vector search → context assembly → Groq LLM generation.
- **4 Chunking Strategies**: Fixed window, sliding window (sentence-boundary aware), structure-based (Markdown headings), and semantic (embedding similarity). Each strategy writes to an isolated Qdrant collection.
- **Evaluation Engine**: Automated benchmark pipeline with LLM-as-judge scoring (faithfulness + relevance), retrieval precision@k, latency percentiles, and per-query cost tracking. Supports balanced sampling across research and synthetic datasets.
- **Redis Caching**: Query response cache (hash-based lookup) and embedding cache to avoid recomputation. Feature-flag controlled via `CACHE_ENABLED` and `EMBEDDING_CACHE_ENABLED`.
- **Async Ingestion**: `POST /documents/text/async` returns a job ID immediately, processes in background, and tracks status in Redis.
- **PDF Support**: Ingestion pipeline handles `.md`, `.txt`, and `.pdf` files via PyMuPDF.
- **Structured JSON Logging**: All logs output as JSON with timestamps, module names, and correlation IDs. Request middleware injects a unique `X-Request-ID` header.
- **Rate Limiting**: Sliding-window rate limiter (60 req/min per API key) backed by Redis. Fails open if Redis is unavailable.
- **Docker Deployment**: Multi-stage Dockerfile (build + runtime), docker-compose with Redis, Qdrant, and API service. Includes healthchecks.
- **CI/CD**: GitHub Actions pipeline runs ruff format check → ruff lint → mypy → pytest → Docker build on every push and PR.
- **Streamlit Dashboard**: Retriever Arena (live strategy comparison) and Metrics Laboratory (benchmark visualization).
- **5 Architecture Decision Records**: Vector DB choice, LLM provider, metadata store, interface design, caching strategy.

### Benchmark Results (V2 Post-Refactor)
- Sliding Window achieved highest faithfulness (3.34/5) and lowest hallucination rate (28%).
- All strategies reached ~94% hit rate at k=5, suggesting retrieval precision ceiling requires hybrid search to break.
- See `docs/case_studies/` for full analysis.

### Known Limitations
- Only vector retrieval is implemented. Hybrid search (BM25 + vector) and reranking are planned for Phase 2.
- Single LLM model (Llama-3.1-8b). Cost-based model routing is planned for Phase 5.
- SQLite metadata store. PostgreSQL migration planned for Phase 4.
