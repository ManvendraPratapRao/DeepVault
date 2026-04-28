# Changelog

All notable changes to DeepVault are documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [3.0.0] — Phase 3: Query Intelligence

### Added
- **`QueryClassifier`** (`app/infrastructure/query/classifier.py`): Rule-based query type classifier with ordered regex pattern matching. Classifies queries into `factual`, `semantic`, `comparison`, or `complex` with zero latency overhead (pure in-process, no LLM call).
- **`QueryRouter`** (`app/infrastructure/query/router.py`): Routes each query type to its optimal retrieval strategy based on Phase 2 benchmark findings. Factual → `hybrid`, Semantic → `vector`, Comparison/Complex → `hybrid_rerank`. Activated via `retrieval_strategy: "auto"` in the API request.
- **`QueryDecomposer`** (`app/infrastructure/query/decomposer.py`): LLM-based decomposition for complex multi-part questions. Splits into 2–4 sub-queries, executes all retrievals in parallel via `asyncio.gather()`, then deduplicates by chunk ID. Falls back to original query on LLM failure.
- **v3 Prompt Templates** (`app/prompts/v3/decomposition.py`): Structured decomposition prompt with worked example, enforcing one-sub-query-per-line format (no JSON parsing needed).
- **`retrieval_strategy: "auto"` API support**: Query endpoint now accepts `"auto"` as a strategy value. When used, the router classifies the query and selects the best strategy automatically.
- **25+ classifier/router unit tests** (`tests/unit/test_query_router.py`): Covering all 4 query types, boundary cases, and routing table correctness. Pass in 0.77s with no infrastructure.
- **ADR-009** (`docs/adrs/009-query-routing-strategy.md`): Documents the rule-based vs LLM-based vs embedding-based classification decision.
- **ADR-010** (`docs/adrs/010-query-decomposition.md`): Documents the LLM decomposition decision, including parallel retrieval architecture and deduplication strategy.

### Changed
- `QueryService.__init__()`: Added `router: QueryRouter | None` and `decomposer: QueryDecomposer | None` parameters (backward compatible — both default to `None`).
- `QueryService.ask()`: Now calls router when `retrieval_strategy == "auto"`, and calls decomposer for `complex` query type.
- `dependencies.py`: Added `get_query_router()` and `get_query_decomposer()` factory functions. `get_query_service()` now wires both.
- `settings.RETRIEVAL_STRATEGY`: Added `"auto"` as a valid value alongside `vector`, `hybrid`, `hybrid_rerank`.

## [2.1.0] — Phase 4 Production Hardening (Partial)

### Added
- **Prometheus Metrics** (`app/api/middleware/metrics.py`): 7 application-level metrics instrumented across the full stack — HTTP request counts/latency, RAG query counts/latency/cost, cache hit/miss rates, and ingestion success/duplicate/error counts. All services call the helpers (`record_query_metrics`, `record_cache_op`, `record_ingestion`).
- **`/metrics` Endpoint**: Prometheus scrape endpoint mounted at `/metrics` via `make_asgi_app()`. HTTP-level instrumentation via inline middleware (skips self-loop).
- **Grafana + Prometheus in Docker Compose**: Full observability stack in `docker/docker-compose.yml`. Grafana provisioned via `docker/grafana/provisioning/` with `deepvault_overview.json` dashboard. Access at `http://localhost:3000` (admin/deepvault).
- **SSE Streaming Endpoint** (`POST /api/v1/stream`): Server-Sent Events endpoint that yields LLM tokens as they are produced. Returns `data: <token>`, `data: [DONE]`, or `data: [ERROR] <msg>` sentinels. No buffering via `X-Accel-Buffering: no` header.
- **`GroqLLMClient.stream()`**: Async generator that streams Groq completions token-by-token.
- **Streaming Chat UI** (`app/ui/pages/3_Chat.py`): ChatGPT-style interface that consumes the SSE stream via `httpx`. Blinking cursor animation during streaming, source citations, latency badge.
- **Detailed Health Check** (`GET /api/v1/health/detailed`): Probes Redis, Qdrant, and LLM with per-component latency. Returns `healthy` / `degraded` based on dependency availability.
- **Streaming Unit Tests** (`tests/unit/test_streaming.py`): 5 tests covering token yield, retriever invocation, empty retrieval error path, cache replay, and reranking integration.
- **Query Rewriter Tests** (`tests/unit/test_rewriter.py`): 6 tests covering query expansion patterns and graceful fallback on LLM failure.
- **API Route Tests** (`tests/api/test_routes.py`): 12 tests covering health, query, ingest, and metrics routes with dependency injection mocks.

### Fixed
- `seed.py`: Removed mutation of global `settings.CHUNKER_SIZE` / `settings.CHUNKER_OVERLAP`. Strategy-specific chunk sizes are now resolved locally without side effects.
- `IngestionService`: Wired `record_ingestion()` Prometheus metric — now called on success, duplicate, and error paths.
- Qdrant `search()`: Migrated to `NearestQuery` model to prevent internal `OffsetZero` panics on some SDK versions.
- `BaseVectorStore` ABC: Added `collection_name` parameter to `search()` signature (LSP violation fix).
- `ingest_directory()`: Now correctly globs `.pdf` files (was missing from the pattern).
- Duplicate detection: Now uses `get_document_by_hash()` instead of raw SQL.

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
