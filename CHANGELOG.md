# Changelog

All notable changes to DeepVault are documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/).

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
