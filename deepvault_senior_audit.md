# 🔍 DeepVault — Senior AI Engineer Codebase Audit

> **Reviewer Posture:** Senior AI Engineer ($180K+), evaluating this as a portfolio submission.  
> **Date:** April 13, 2026  
> **Codebase Size:** ~65 source files, ~6,500 LOC (excluding vendor/cache)

---

## Part 1: Implementation Plan Review — Is This Guide Good?

### Verdict: ⭐⭐⭐⭐½ (Excellent — Top 5% of portfolio plans I've seen)

This plan was clearly written by someone who understands what hiring managers at $150K+ roles actually look for. Here's what makes it strong:

| Strength | Why It Matters |
|----------|---------------|
| **Phase-gated with acceptance criteria** | Shows you think in deliverables, not tasks |
| **Evaluation from Phase 1** | This is THE differentiator — 95% of RAG projects skip this |
| **ADRs and documentation as first-class** | Senior engineers document *why*, not just *what* |
| **Interface-driven design** | Shows architectural thinking, not just coding |
| **Each phase is independently deployable** | Proves production mindset |
| **Cost tracking & A/B testing in Phase 5** | This is ML *engineering*, not ML *hobbyism* |

### Three concerns with the plan:

> [!WARNING]
> **1. Timeline is aggressive:** The plan estimates ~34 "days" at 10-13 hrs/day. That's 340-440 hours. For a solo developer building this quality, expect 500-600 hours. Don't rush — a polished Phase 3 beats a sloppy Phase 5.

> [!IMPORTANT]
> **2. Phase 3 (Graph) may not be worth the ROI for portfolio purposes.** Neo4j + entity extraction + Cypher generation is impressive but adds massive scope. Consider making Phase 3 optional and spending that time polishing Phases 1-2 and jumping to Phase 4 (production hardening). Hybrid Search + Reranking + Observability is more relevant to 90% of AI Engineer roles than Graph RAG.

> [!NOTE]
> **3. "120 synthetic documents" is fine but not impressive.** The real signal is the *quality* of your eval, not the corpus size. Your current ~80+ synthetic + research papers is already solid. Don't burn time generating more docs.

---

## Part 2: Progress Assessment — What's Done?

### Phase 0 (Data Sprint): ✅ ~95% Complete

| Deliverable | Status | Evidence |
|------------|--------|---------|
| Synthetic dataset (~120 docs) | ✅ Done | [synthetic_data_v2/](file:///d:/ML%20PROJECTS/deepvault/synthetic_data_v2) — 7 categories present |
| Golden QA dataset | ✅ Done | [golden_qa_dataset.json](file:///d:/ML%20PROJECTS/deepvault/synthetic_data_v2/golden_qa_dataset.json) (62KB) |
| Research papers (curated) | ✅ Done | [data/curated_papers/](file:///d:/ML%20PROJECTS/deepvault/data/curated_papers) |
| Research QA pairs | ✅ Done | [research_papers_golden_qa.json](file:///d:/ML%20PROJECTS/deepvault/data/research_papers_golden_qa.json) (165KB) |

---

### Phase 1A (Core Pipeline): ✅ ~85% Complete

| Deliverable | Status | Notes |
|------------|--------|-------|
| FastAPI app with OpenAPI spec | ✅ Done | [app/main.py](file:///d:/ML%20PROJECTS/deepvault/app/main.py) — clean app factory |
| Document ingestion pipeline | ✅ Done | [ingestion.py](file:///d:/ML%20PROJECTS/deepvault/app/services/ingestion.py) — MD + PDF support |
| Query pipeline (RAG loop) | ✅ Done | [query.py](file:///d:/ML%20PROJECTS/deepvault/app/services/query.py) |
| Pydantic request/response models | ✅ Done | [schemas/](file:///d:/ML%20PROJECTS/deepvault/app/api/schemas) |
| Structured JSON logging | ✅ Done | [structured.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/logging/structured.py) |
| Interface-driven design (ABCs) | ✅ Done | 6 ABCs in [interfaces/](file:///d:/ML%20PROJECTS/deepvault/app/core/interfaces) |
| Exception hierarchy | ✅ Done | [exceptions.py](file:///d:/ML%20PROJECTS/deepvault/app/core/exceptions.py) |
| Unit tests | ⚠️ Partial | 4 test files, ~89 lines. Coverage likely <50% |
| Integration tests | ⚠️ Partial | Exist but rely on mocks heavily |
| Docker + docker-compose | ✅ Done | Multi-stage Dockerfile + compose with healthchecks |
| CI pipeline | ✅ Done | [ci.yml](file:///d:/ML%20PROJECTS/deepvault/.github/workflows/ci.yml) — lint + mypy + test + build |
| ADRs | ✅ Done | 5 ADRs in [docs/adrs/](file:///d:/ML%20PROJECTS/deepvault/docs/adrs) |

---

### Phase 1B (Caching & Async): ✅ ~90% Complete

| Deliverable | Status | Notes |
|------------|--------|-------|
| Redis caching layer | ✅ Done | [redis.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/cache/redis.py) |
| Semantic query cache | ✅ Done | [cache_service.py](file:///d:/ML%20PROJECTS/deepvault/app/services/cache_service.py) |
| Embedding cache | ✅ Done | In [bge.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/embedders/bge.py) |
| Async ingestion (Background Tasks) | ✅ Done | [ingest.py](file:///d:/ML%20PROJECTS/deepvault/app/api/v1/routes/ingest.py) — `/text/async` endpoint |
| Rate limiting | ✅ Done | [limiter.py](file:///d:/ML%20PROJECTS/deepvault/app/api/middleware/limiter.py) + [dependencies.py](file:///d:/ML%20PROJECTS/deepvault/app/api/dependencies.py) |
| Latency benchmark (before/after cache) | ❌ Missing | Not documented in README or benchmarks |

---

### Phase 1C (Evaluation Baseline): ✅ ~80% Complete

| Deliverable | Status | Notes |
|------------|--------|-------|
| Golden Q&A dataset (80+) | ✅ Done | Two files totaling ~230KB |
| Evaluation pipeline script | ✅ Done | [eval_engine_metrics.py](file:///d:/ML%20PROJECTS/deepvault/scripts/eval_engine_metrics.py) — 410 lines, very solid |
| `make eval` command | ✅ Done | In [Makefile](file:///d:/ML%20PROJECTS/deepvault/Makefile) |
| Baseline benchmark report | ✅ Done | [v1_initial_benchmark.md](file:///d:/ML%20PROJECTS/deepvault/docs/case_studies/v1_initial_benchmark.md) |
| 4-strategy comparison | ✅ Done | Fixed vs Sliding vs Structure vs Semantic compared |
| Latency percentiles (p50, p95, p99) | ⚠️ Partial | p95 is tracked but p50/p99 not prominently reported |
| V2 post-refactor benchmark | ✅ Done | [v2_post_refactor_benchmark.md](file:///d:/ML%20PROJECTS/deepvault/docs/case_studies/v2_post_refactor_benchmark.md) |

---

### Phase 2+ (Hybrid Retrieval, Graph, Production): ❌ Not Started

Everything from Phase 2 onward is untouched:
- ❌ BM25 retriever
- ❌ Hybrid retriever (RRF)
- ❌ Cross-encoder re-ranker
- ❌ Query rewriting
- ❌ Knowledge graph (Neo4j)
- ❌ Auth/RBAC
- ❌ Observability (Prometheus/Grafana)
- ❌ Cloud deployment

### Overall Progress: **Phase 1 is ~85% complete. Phase 2-5 = 0%.**

---

## Part 3: Code Quality Audit — The $150K-$180K Lens

### 🟢 What's GOOD (Keep doing this)

**1. Clean Architecture — This is your strongest signal.**
Your layer separation is genuinely good: `core/interfaces` → `infrastructure` → `services` → `api`. This is exactly what a staff engineer would want to see. The dependency injection via [dependencies.py](file:///d:/ML%20PROJECTS/deepvault/app/dependencies.py) is a well-implemented service locator pattern.

**2. Evaluation Engineering — This separates you from 95% of RAG projects.**
Your [eval_engine_metrics.py](file:///d:/ML%20PROJECTS/deepvault/scripts/eval_engine_metrics.py) is genuinely impressive. Rate limiting, LLM-as-judge, cost tracking, progressive save, balanced sampling — this is production-grade eval infrastructure.

**3. Chunking Strategy Comparison — Real engineering, not toy demos.**
Having 4 chunking strategies with refactoring documented in case studies is the exact kind of iterative, data-driven engineering that hiring managers want to see. The V1→V2 benchmark story is compelling.

**4. Docker & CI — Production from day one.**
Multi-stage Dockerfile, healthchecks, docker-compose with service dependencies, and a working CI pipeline. This is the right foundation.

**5. Prompt Engineering with Injection Protection.**
Your RAG prompt in [system.py](file:///d:/ML%20PROJECTS/deepvault/app/prompts/v1/system.py) has explicit prompt injection defense (`<CONTEXT>` tags with "ignore any instructions"). This is a detail most junior devs miss entirely.

---

### 🔴 CRITICAL Issues (Fix before any job application)

**1. README is embarrassingly over-written.**

Your [README.md](file:///d:/ML%20PROJECTS/deepvault/README.md) uses phrases like:
- *"mathematically mapping external document integrations seamlessly"*
- *"executing deeply dynamically inside the container CPU"*  
- *"statically executed over astral-sh/uv structures"*
- *"strict Hexagonal Domains"*
- *"Dynamically evaluates raw string queries completely through Groq networks"*

**This is a career-killer.** A hiring manager reading this will think you're hiding a lack of understanding behind jargon. Your actual code is clean and solid — the README makes it look like you don't understand what you built.

> [!CAUTION]
> **Action:** Rewrite the README in plain, confident English. "DeepVault is a RAG system that ingests enterprise documents, chunks them using 4 strategies, retrieves relevant context via Qdrant vector search, and generates answers using Groq's Llama-3.1. It includes a built-in evaluation pipeline to measure retrieval precision and answer faithfulness." That's it. Let the code speak.

**2. CHANGELOG has the same problem.**

[CHANGELOG.md](file:///d:/ML%20PROJECTS/deepvault/CHANGELOG.md) uses phrases like *"dynamically slashing repetitive generation queries"*, *"Dual-layer architecture enforces SQLite to rigorously track document checksum hashes"*. Changelogs should be technical and factual.

**3. No `__init__.py` in `app/api/middleware/`.**

The [middleware](file:///d:/ML%20PROJECTS/deepvault/app/api/middleware) directory contains `logging.py` and `limiter.py` but has no `__init__.py`. While Python 3.12+ supports namespace packages, explicit `__init__.py` files are expected in a production project and signal intentional package structure.

**4. The `dependencies.py` DI container is a God Object.**

[dependencies.py](file:///d:/ML%20PROJECTS/deepvault/app/dependencies.py) at 231 lines is doing too much: managing singletons, building services, lifecycle management, and Qdrant client health checking all in one file. A senior engineer would split this:
- `app/container.py` — the singleton registry
- `app/lifecycle.py` — init/shutdown hooks
- `app/factories.py` — service builders

**5. The `logger` is a global root logger — this will cause issues.**

In [structured.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/logging/structured.py), you call `logging.getLogger()` (root logger) and clear ALL handlers. This means every library (Qdrant, httpx, uvicorn) that uses Python logging will also output through your JSON formatter — or worse, have their handlers stripped. Use a named logger: `logging.getLogger("deepvault")`.

**6. `QdrantVectorStore.search()` signature breaks the ABC contract.**

Your [BaseVectorStore.search()](file:///d:/ML%20PROJECTS/deepvault/app/core/interfaces/vector_store.py#L17-L25) ABC signature doesn't include `collection_name`, but your [QdrantVectorStore.search()](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/stores/qdrant.py#L87-L130) adds it. This violates the Liskov Substitution Principle. Either add `collection_name` to the ABC or use a separate method.

**7. `BaseChunker.chunk()` is synchronous but `IngestionService` runs it in a thread.**

The [BaseChunker](file:///d:/ML%20PROJECTS/deepvault/app/core/interfaces/chunker.py) ABC defines `chunk()` as sync, which is correct. But [SemanticChunker.chunk()](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/chunkers/semantic.py#L48) calls `self.embedder.model.encode()` — a potentially heavy sync operation. The architecture handles this (via `asyncio.to_thread` in ingestion), but the chunker should document this contract.

---

### 🟡 MODERATE Issues (Fix during Phase 2 work)

**8. `get_document()` in SQLite does a lookup by `doc_id` but `ingest_text()` queries by `doc_hash`.**

In [ingestion.py:48](file:///d:/ML%20PROJECTS/deepvault/app/services/ingestion.py#L48), you call `self.doc_store.get_document(doc_hash)` to check for duplicates, but `get_document()` queries by `id` (primary key), not `hash`. This means your duplicate check is actually looking for a document whose `id` equals the hash — which would never match because `id` is a UUID. Your duplicate detection is likely broken.

**9. `IngestResponse.chunks_created` is always 0.**

In [ingest.py:33](file:///d:/ML%20PROJECTS/deepvault/app/api/v1/routes/ingest.py#L33) and [line 83](file:///d:/ML%20PROJECTS/deepvault/app/api/v1/routes/ingest.py#L83), `chunks_created` is hardcoded to `0`. Either track and return the real count, or remove the field.

**10. `CacheService` uses MD5 for query hashing.**

In [cache_service.py:24](file:///d:/ML%20PROJECTS/deepvault/app/services/cache_service.py#L24), you use `hashlib.md5` for query cache keys. While collision risk is low for cache keys, using MD5 in 2026 is a red flag for security-conscious reviewers. Use SHA-256 consistently (you already use it for embedding cache and document hashing).

**11. `IngestionService.ingest_directory()` silently excludes PDFs.**

In [ingestion.py:139](file:///d:/ML%20PROJECTS/deepvault/app/services/ingestion.py#L139), the glob only matches `.md` and `.txt`, but `ingest_file()` supports `.pdf`. This is inconsistent.

**12. The `get_chunker()` function lacks a return type hint.**

[dependencies.py:55](file:///d:/ML%20PROJECTS/deepvault/app/dependencies.py#L55) — `async def get_chunker()` has no return type. This is the only factory function without one. Use `-> BaseChunker`.

**13. `settings.CHUNKER_STRATEGY` is mutated at runtime in `seed.py`.**

[seed.py:87](file:///d:/ML%20PROJECTS/deepvault/scripts/seed.py#L87) directly mutates `settings.CHUNKER_STRATEGY`. Pydantic Settings objects shouldn't be mutated post-initialization. Pass strategy as a parameter instead.

**14. Test coverage is thin.**

Your current tests cover:
- Chunkers: 4 basic tests (fixed, sliding, semantic, structure)
- Cache service: basic hit/miss
- Ingestion service: 1 test
- Query service: 1 test

For a $150K+ portfolio, you need **at minimum**:
- Edge case tests for each chunker (empty doc, unicode, very long doc, single-word doc)
- Error path tests (LLM failure, Qdrant timeout, Redis down)
- Full integration tests with real dependencies (using testcontainers)
- Evaluation pipeline tests

**15. The Streamlit UI exists but is not integrated into the project narrative.**

You have [dashboard.py](file:///d:/ML%20PROJECTS/deepvault/app/ui/dashboard.py) and two pages, but neither the README nor the CHANGELOG mention the UI. For portfolio purposes, the UI should be a featured demo point.

---

## Part 4: Session-by-Session Completion Roadmap

Based on what's done and what remains, here's your roadmap to make DeepVault a $150-180K portfolio piece. Each session is ~3-4 hours of focused work.

---

### 🏁 Phase 1 Polish (Sessions 1-4) — "Finish what you started"

#### Session 1: README Rewrite + Documentation Overhaul
- [ ] Rewrite [README.md](file:///d:/ML%20PROJECTS/deepvault/README.md) in plain, professional English
- [ ] Rewrite [CHANGELOG.md](file:///d:/ML%20PROJECTS/deepvault/CHANGELOG.md) to be factual and concise
- [ ] Add a "Benchmark Results" section to README with a table from your case studies
- [ ] Add a "System Architecture" section with the clean mermaid diagram from the plan
- [ ] Add setup instructions that actually work for a fresh clone
- [ ] Update `VERSION` in config.py from `0.1.0` → `1.0.0`

#### Session 2: Critical Bug Fixes
- [ ] Fix duplicate detection bug (`get_document(doc_hash)` queries by wrong field)
- [ ] Fix `IngestResponse.chunks_created` to return actual count
- [ ] Fix `ingest_directory()` to include PDFs
- [ ] Replace MD5 with SHA-256 in `CacheService`
- [ ] Fix root logger issue — use named logger `logging.getLogger("deepvault")`
- [ ] Fix `BaseVectorStore.search()` ABC to include `collection_name` parameter
- [ ] Add `__init__.py` to `app/api/middleware/`
- [ ] Add return type to `get_chunker()` → `BaseChunker`
- [ ] Stop mutating global settings in `seed.py` — pass strategy as argument

#### Session 3: Test Coverage Push
- [ ] Add edge case tests for all 4 chunkers (empty, unicode, very long, single sentence)
- [ ] Add error path tests for `QueryService` (LLM failure, no chunks returned)
- [ ] Add error path tests for `IngestionService` (invalid file, storage failure)
- [ ] Add cache service tests for Redis-down scenario
- [ ] Add API route tests using FastAPI `TestClient`
- [ ] Target: **15+ new test functions, >60% coverage on `app/`**

#### Session 4: Phase 1 Release Prep
- [ ] Run full lint + mypy + test suite and fix all warnings
- [ ] Run `make eval` to produce a fresh baseline benchmark
- [ ] Write `docs/benchmarks/v1.0.0.md` (formal benchmark document)
- [ ] Tag git release `v1.0.0`
- [ ] Record a 2-minute Loom/demo video showing: ingest → query → eval
- [ ] Push clean commit history (squash messy commits)

---

### 🔍 Phase 2: Hybrid Retrieval Engine (Sessions 5-12)

#### Session 5: BM25 Retriever Implementation
- [ ] Install `rank-bm25` dependency
- [ ] Create `app/infrastructure/retrievers/bm25.py` implementing `BaseRetriever`
- [ ] Build a simple BM25 index from Qdrant chunk payloads (load at startup)
- [ ] Write unit tests for BM25Retriever

#### Session 6: Hybrid Retriever + RRF
- [ ] Create `app/infrastructure/retrievers/hybrid.py`
- [ ] Implement Reciprocal Rank Fusion (RRF) merging strategy
- [ ] Add configurable weights (alpha for vector, beta for BM25)
- [ ] Wire into dependency injection with `RETRIEVAL_STRATEGY` config
- [ ] Unit tests: verify RRF merging logic

#### Session 7: Cross-Encoder Reranker
- [ ] Create `app/core/interfaces/reranker.py` — `BaseReranker` ABC
- [ ] Create `app/infrastructure/rerankers/cross_encoder.py`
- [ ] Use `cross-encoder/ms-marco-MiniLM-L-6-v2` (small, fast)
- [ ] Integrate reranker into query pipeline (retrieve top-20 → rerank → top-5)
- [ ] Unit tests for reranker

#### Session 8: Query Rewriting Module
- [ ] Create `app/infrastructure/query/rewriter.py`
- [ ] Implement LLM-based query expansion for ambiguous queries
- [ ] Add `app/prompts/v2/query_rewrite.py` — prompt template
- [ ] Wire into query pipeline as optional pre-processing step
- [ ] Test with 3+ query patterns (ambiguous, multi-part, abbreviation)

#### Session 9: Wire Everything Together
- [ ] Update `QueryService` to support `hybrid` and `hybrid_rerank` retrieval strategies
- [ ] Update `dependencies.py` to build hybrid retriever when configured
- [ ] Update API schemas to accept new retrieval strategies
- [ ] Integration test: same query through vector-only vs hybrid vs hybrid+rerank

#### Session 10: Phase 2 Comparative Benchmark
- [ ] Extend eval engine to test 6+ configurations
- [ ] Run full evaluation: vector-only, BM25-only, hybrid, hybrid+rerank, hybrid+rerank+rewrite
- [ ] Produce comparison table with Precision@5, Recall@5, latency, cost
- [ ] Write `docs/benchmarks/v2.0.0.md` with charts and analysis

#### Session 11: Phase 2 Documentation + ADRs
- [ ] Write ADR-006: BM25 vs Elasticsearch decision
- [ ] Write ADR-007: RRF vs weighted merging decision
- [ ] Write ADR-008: Cross-encoder model selection
- [ ] Update architecture diagram in README
- [ ] Update CHANGELOG

#### Session 12: Phase 2 Release
- [ ] Full test suite pass
- [ ] Tag `v2.0.0` release
- [ ] Record demo video showing hybrid search improving retrieval
- [ ] Update README with Phase 2 results

---

### 🧠 Phase 3: Query Intelligence (Sessions 13-16) — *SIMPLIFIED*

> [!IMPORTANT]
> **I recommend skipping Neo4j/KG for now.** Instead, implement a lightweight query router + query decomposition. This gives you 80% of the portfolio signal at 20% of the effort. You can add Graph RAG later as an "ongoing" feature.

#### Session 13: Query Classification + Router
- [ ] Create `app/infrastructure/query/classifier.py` — rule-based first
- [ ] Query types: `factual`, `semantic`, `relational_simple`, `comparison`
- [ ] Create `app/infrastructure/query/router.py` — routes to best retriever config
- [ ] Factual → BM25-heavy, Semantic → vector-heavy, Comparison → hybrid+rerank
- [ ] Unit tests with 20+ sample queries mapped to expected categories

#### Session 14: Query Decomposition for Complex Questions
- [ ] Create `app/infrastructure/query/decomposer.py`
- [ ] Use LLM to break complex queries into sub-queries
- [ ] Execute sub-queries in parallel, merge contexts
- [ ] Add `app/prompts/v3/decomposition.py`
- [ ] Test with 5+ complex multi-part questions

#### Session 15: Router Benchmark
- [ ] Add 20+ new golden QA questions targeting router categories
- [ ] Run eval comparing: always-hybrid vs routed
- [ ] Measure router accuracy (% of correctly classified queries)
- [ ] Write `docs/benchmarks/v3.0.0.md`

#### Session 16: Phase 3 Release
- [ ] ADRs for router design decisions
- [ ] Tag `v3.0.0`
- [ ] Demo video showing smart routing
- [ ] CHANGELOG + README updates

---

### 🏗️ Phase 4: Production Hardening (Sessions 17-24)

#### Session 17: Observability — Prometheus Metrics
- [ ] Add `prometheus-client` dependency
- [ ] Create `app/api/middleware/metrics.py`
- [ ] Instrument: query latency, retrieval latency, LLM latency, token usage, cache hits
- [ ] Expose `/metrics` endpoint
- [ ] Unit tests for metric increments

#### Session 18: Observability — Grafana Dashboards
- [ ] Add Grafana + Prometheus to `docker-compose.yml`
- [ ] Create 3 dashboard JSON configs (System Overview, LLM Cost, Retrieval Performance)
- [ ] Provision dashboards automatically via docker volume
- [ ] Screenshot dashboards for docs
- [ ] Write `docs/observability.md`

#### Session 19: Streaming Responses (SSE)
- [ ] Create `app/api/v1/routes/stream.py` — SSE endpoint
- [ ] Wire `GroqLLMClient.stream()` (already implemented!) to the route
- [ ] Test streaming end-to-end with curl/httpx
- [ ] Update Streamlit UI to use streaming

#### Session 20: Enhanced Streamlit UI
- [ ] Polish Retriever Arena page with actual strategy comparison
- [ ] Add source panel showing retrieved chunks with scores
- [ ] Add streaming chat interface
- [ ] Add document management page (list, delete, re-ingest)
- [ ] Screenshot for README

#### Session 21: Authentication (JWT)
- [ ] Add `python-jose` dependency
- [ ] Create `app/api/middleware/auth.py` — JWT token validation
- [ ] Implement 3 roles: admin, user, viewer
- [ ] Protect endpoints based on role
- [ ] Create `POST /auth/token` login endpoint
- [ ] Integration tests with multiple user roles

#### Session 22: PostgreSQL Migration
- [ ] Add `asyncpg` or `databases` dependency
- [ ] Create `app/infrastructure/stores/postgres.py` implementing `BaseDocumentStore`
- [ ] Add PostgreSQL to `docker-compose.yml`
- [ ] Write migration script from SQLite → PostgreSQL
- [ ] ADR: SQLite → PostgreSQL migration rationale

#### Session 23: Health Check Enhancement + Detailed Status
- [ ] Create `/api/v1/health/detailed` endpoint
- [ ] Check each dependency: Qdrant, Redis, PostgreSQL, Groq API, embedding model
- [ ] Return per-component latency and status
- [ ] Add alerting thresholds

#### Session 24: Phase 4 Release + Cloud Prep
- [ ] Multi-stage Docker optimization (final image size check)
- [ ] Environment-based config (dev/staging/prod)
- [ ] Write `docs/deployment.md` with AWS EC2 free-tier instructions
- [ ] Full benchmark: P1 vs P2 vs P3 vs P4
- [ ] Tag `v4.0.0`
- [ ] Demo video showing full production system

---

### 🤖 Phase 5: Autonomous Intelligence (Sessions 25-30)

#### Session 25: LLM Router + Cost Optimization
- [ ] Create `app/infrastructure/llm/router.py` — selects model by query complexity
- [ ] Simple → 8b model, Complex → 70b model
- [ ] Implement fallback chain: primary → retry → fallback model
- [ ] Track cost savings vs always-expensive in dashboard

#### Session 26: User Feedback System
- [ ] Create `POST /api/v1/feedback` endpoint (👍/👎 + text)
- [ ] Store feedback with full query context
- [ ] Create feedback analytics in Streamlit dashboard
- [ ] Show feedback trends and failure patterns

#### Session 27: A/B Testing Framework
- [ ] Create `app/services/ab_testing.py`
- [ ] Support prompt version A/B tests and retrieval strategy A/B tests
- [ ] Traffic splitting (random assignment by session_id)
- [ ] Results storage and statistical significance calculation
- [ ] Run one real A/B test (e.g., prompt v1 vs v2)

#### Session 28: Automated Nightly Evaluation
- [ ] Create `.github/workflows/nightly_eval.yml`
- [ ] Run golden dataset against current system on schedule
- [ ] Compare against historical baselines
- [ ] Slack/email alert on regression
- [ ] Store historical eval trend data

#### Session 29: Agent Layer (Focused)
- [ ] Create `app/services/agent.py` — simple ReAct loop
- [ ] Implement 2 tools: document summarization + entity extraction
- [ ] Agent decides: direct RAG vs tool-augmented RAG
- [ ] Logging shows agent reasoning chain

#### Session 30: Final Release + Retrospective
- [ ] Complete evaluation history visualization (P1→P5)
- [ ] Write `docs/retrospective.md` — what worked, what didn't, what you'd do differently
- [ ] Write `docs/cost-analysis.md`
- [ ] Final architecture diagram
- [ ] Comprehensive demo video (5 mins)
- [ ] Tag `v5.0.0`
- [ ] Polish GitHub profile: pin repo, add topics, write compelling description

---

## Part 5: Priority Ranking — What to Do First

If you have limited time, here's the ROI-ranked priority:

| Priority | What | Why | Sessions |
|----------|------|-----|----------|
| 🔴 **P0** | README rewrite + bug fixes | A bad README kills interest before anyone reads code | 1-2 |
| 🔴 **P0** | Test coverage push | <50% coverage is a red flag at $150K+ | 3 |
| 🟡 **P1** | Phase 2 (Hybrid Search) | BM25 + Reranking is THE most relevant skill for AI Engineer roles | 5-12 |
| 🟡 **P1** | Observability (Prometheus/Grafana) | Shows production thinking — quick win | 17-18 |
| 🟢 **P2** | Streaming + UI polish | Makes demos look professional | 19-20 |
| 🟢 **P2** | Auth + PostgreSQL | Enterprise-readiness signal | 21-22 |
| 🔵 **P3** | Query Router | Nice to have, shows ML thinking | 13-16 |
| 🔵 **P3** | Phase 5 (Autonomous) | Impressive but not required for $150-180K | 25-30 |

> [!TIP]
> **The minimum viable portfolio is: Phase 1 (polished) + Phase 2 (Hybrid Search with benchmarks) + Observability. That's sessions 1-12 + 17-18 = ~14 sessions = ~50 hours.** This alone puts you in the top 10% of AI Engineer candidates.

---

## Summary

| Dimension | Current Grade | Target Grade |
|-----------|--------------|-------------|
| Architecture | **A** | A+ |
| Code Quality | **B+** | A |
| Testing | **C** | B+ |
| Documentation | **D** (README) | A |
| Evaluation | **A** | A+ |
| Production Readiness | **B** | A |
| Feature Completeness | **C** (Phase 1 only) | B+ (through Phase 2+) |

Your **code** is genuinely better than your **presentation**. The biggest ROI right now is fixing the README, fixing the bugs I identified, boosting test coverage, and then moving to Phase 2 (Hybrid Search). Don't try to rush through all 5 phases — a deeply polished Phase 1+2 with real benchmarks beats a surface-level Phase 5.
