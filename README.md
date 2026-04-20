# DeepVault — Enterprise RAG Platform

DeepVault is a production-grade Retrieval-Augmented Generation (RAG) system built from scratch using interface-driven design. It ingests enterprise documents (Markdown, text, PDF), chunks them using 4 configurable strategies, stores embeddings in Qdrant, and generates grounded answers using Groq's Llama-3.1.

The system includes a built-in evaluation pipeline that measures retrieval precision, answer faithfulness, and cost efficiency — enabling data-driven decisions about chunking and retrieval strategies.

## Key Features

- **4 Chunking Strategies** — Fixed window, sliding window, structure-based (Markdown headings), and semantic (embedding similarity). Each strategy creates an isolated Qdrant collection for side-by-side comparison.
- **Async Ingestion Pipeline** — Background document processing with job tracking and duplicate detection via content hashing.
- **Redis Caching** — Semantic query cache (MD5 → cached response) and embedding cache to avoid recomputation.
- **Evaluation Engine** — Automated benchmarking with LLM-as-judge scoring (faithfulness + relevance), retrieval precision@k, latency percentiles, and cost tracking.
- **Rate Limiting** — Per-API-key sliding window rate limiter backed by Redis.
- **Structured JSON Logging** — Every request gets a correlation ID; all logs output as structured JSON for observability.
- **Streamlit Dashboard** — Interactive Retriever Arena for live strategy comparison and Metrics Laboratory for benchmark analysis.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **API Framework** | FastAPI (Python 3.13) via [uv](https://github.com/astral-sh/uv) |
| **LLM Inference** | Groq (Llama-3.1-8b-instant) |
| **Vector Database** | Qdrant (local or Docker) |
| **Embedding Model** | BAAI/bge-small-en-v1.5 (384-dim, runs on CPU) |
| **Metadata Store** | SQLite (async via aiosqlite) |
| **Caching** | Redis 7 |
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions (lint → type-check → test → build) |

## System Architecture

```mermaid
graph TD
    subgraph API Layer
        FE[Streamlit UI] --> API[FastAPI /api/v1]
    end

    subgraph Service Layer
        API --> IS[Ingestion Service]
        API --> QS[Query Service]
        API --> DS[Document Service]
    end

    subgraph Core Abstractions
        IS -.-> CH[BaseChunker]
        IS -.-> EM[BaseEmbedder]
        IS -.-> VS[BaseVectorStore]
        IS -.-> MS[BaseDocumentStore]
        QS -.-> RT[BaseRetriever]
        QS -.-> LLM[BaseLLMClient]
        QS -.-> CS[CacheService]
    end

    subgraph Infrastructure
        CH --> C1[FixedWindowChunker]
        CH --> C2[SlidingWindowChunker]
        CH --> C3[StructureChunker]
        CH --> C4[SemanticChunker]
        RT --> VR[VectorRetriever]
        LLM --> GR[GroqLLMClient]
        EM --> BGE[BgeEmbedder]
        VS --> QD[(Qdrant)]
        MS --> SQL[(SQLite)]
        CS --> RD[(Redis)]
    end
```

All components are programmed against abstract base classes (`app/core/interfaces/`), making it straightforward to swap implementations (e.g., replace Qdrant with Pinecone, or Groq with OpenAI) without touching business logic.

## Benchmark Results

We ran 135 questions across **6 retrieval strategies × 4 chunking strategies** using `llama-3.3-70b-versatile` as the LLM judge (faithfulness + relevance scoring).

### Phase 2 Results — Best Configuration per Retrieval Strategy (Fixed Chunking)

| Retrieval Strategy | Faithfulness ↑ | Hallucination Rate ↓ | CP@1 ↑ | Cost/1K |
|-------------------|---------------|---------------------|--------|---------|
| `vector` (Phase 1 baseline) | 3.20 / 5 | 37.5% | 71.4% | 5.82¢ |
| **`hybrid` (BM25 + Vector RRF)** 🏆 | **3.30 / 5** | **28.6%** | 71.4% | 5.88¢ |
| `hybrid_rerank` (+ Cross-Encoder) | 3.02 / 5 | 41.1% | 71.4% | 5.86¢ |
| `vector_rewrite` (+ Query Expansion) | 3.03 / 5 | 46.7% | 63.3% | 5.79¢ |

*Fixed chunking strategy (600 chars, 120 char overlap). Judge: `llama-3.3-70b-versatile`.*

**Key Phase 2 Findings:**
- **Hybrid retrieval reduces hallucinations by 8.9 percentage points** vs vector-only (28.6% → 37.5%), with no latency penalty at p50.
- BM25 excels at exact-keyword queries (product names, acronyms, standards like ISO 27001) that dense vector search frequently misses.
- Cross-encoder reranking adds latency (~100-200ms) with mixed quality improvements at this corpus size.
- Query rewriting is not a universal improvement — it benefits structure-based chunks but degrades sliding window recall.

Full benchmark analysis: [Phase 2 Benchmark](docs/benchmarks/v2.0.0.md) | [V1 Initial](docs/case_studies/v1_initial_benchmark.md) | [V2 Post-Refactor](docs/case_studies/v2_post_refactor_benchmark.md)

## Quick Start

### Prerequisites
- [Python 3.12+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- [Docker](https://www.docker.com/) (for Redis and Qdrant)
- [Groq API Key](https://console.groq.com/)

### 1. Clone and Install

```bash
git clone https://github.com/ManvendraPratapRao/DeepVault.git
cd DeepVault

# Install dependencies
uv sync
```

### 2. Configure Environment

```bash
# Create .env file with your API key
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
```

### 3. Start Infrastructure (Redis + Qdrant)

```bash
# Start Redis and Qdrant via Docker
make docker-up

# Or without make:
docker compose -f docker/docker-compose.yml up -d
```

### 4. Seed the Knowledge Base

```bash
# Seed all 4 chunking strategy collections
make seed-all

# Or seed a single strategy:
make seed CHUNKER=sliding
```

On Windows without `make`:
```powershell
$env:PYTHONPATH="."; uv run python scripts/seed.py --all-strategies
```

### 5. Start the API

```bash
make dev
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 6. Query the System

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: deepvault_secret_key" \
     -d '{"query_text": "What chunking strategies does DeepVault support?", "top_k": 5}'
```

### 7. Launch the Dashboard (Optional)

```bash
make ui
# Opens Streamlit at http://localhost:8501
```

## Development

| Command | Description |
|---------|-------------|
| `make dev` | Start API with hot-reload |
| `make ui` | Start Streamlit dashboard |
| `make test` | Run full test suite (pytest) |
| `make test-cov` | Run tests with coverage report |
| `make eval` | Run evaluation benchmark (50 questions) |
| `make lint` | Check code style (ruff) |
| `make lint-fix` | Auto-fix lint issues + format |
| `make typecheck` | Run mypy type checking |
| `make seed-all` | Seed all 4 chunking strategies |
| `make reset` | Reset all data stores |
| `make count` | Check Qdrant collection sizes |
| `make docker-up` | Start Redis + Qdrant containers |
| `make docker-down` | Stop containers |

## Project Structure

```
deepvault/
├── app/
│   ├── api/              # FastAPI routes, schemas, middleware
│   ├── core/             # Domain models, interfaces (ABCs), exceptions
│   ├── infrastructure/   # Concrete implementations (Qdrant, Groq, Redis, etc.)
│   ├── services/         # Business logic orchestrators
│   ├── prompts/          # Versioned prompt templates
│   └── ui/               # Streamlit dashboard
├── data/                 # Curated research papers + evaluation results
├── synthetic_data_v2/    # Generated enterprise documents + golden QA dataset
├── scripts/              # Seeding, evaluation, diagnostics
├── tests/                # Unit + integration tests
├── docs/                 # ADRs, architecture docs, case studies
└── docker/               # Dockerfile + docker-compose
```

## Architecture Decision Records

| ADR | Decision | Rationale |
|-----|----------|-----------|
| [001](docs/adrs/001-vector-db-choice.md) | Qdrant over FAISS/ChromaDB | Metadata filtering, production-ready, local + Docker modes |
| [002](docs/adrs/002-llm-provider.md) | Groq (Llama-3.1) over OpenAI | Free tier, low latency via LPU, no vendor lock-in |
| [003](docs/adrs/003-sqlite-for-metadata.md) | SQLite for metadata store | Zero-config, sufficient for Phase 1, async via aiosqlite |
| [004](docs/adrs/004-interface-driven-design.md) | ABCs for all components | Enables strategy pattern, easy testing, future extensibility |
| [005](docs/adrs/005-redis-caching-strategy.md) | Redis for query + embedding cache | Sub-millisecond lookups, TTL-based invalidation |
| [006](docs/adrs/006-bm25-keyword-retrieval.md) | rank-bm25 over Elasticsearch | Zero infra overhead, bootstrapped from Qdrant payloads |
| [007](docs/adrs/007-rrf-fusion-strategy.md) | Reciprocal Rank Fusion over weighted scoring | Score-scale independent, robust to outliers |
| [008](docs/adrs/008-cross-encoder-reranker.md) | ms-marco-MiniLM-L-6-v2 cross-encoder | Best quality/speed tradeoff on CPU, Apache 2.0 license |

## Roadmap

- [x] **Phase 1** — Core RAG pipeline, 4 chunking strategies, Redis caching, evaluation baseline
- [x] **Phase 2** — Hybrid retrieval (BM25 + vector RRF), cross-encoder reranking, query rewriting, Phase 2 benchmark
- [ ] **Phase 3** — Query router (factual/semantic/comparison classification), query decomposition
- [ ] **Phase 4** — Production hardening (JWT auth, Prometheus/Grafana observability, SSE streaming, PostgreSQL, deployment)
- [ ] **Phase 5** — Autonomous optimization (A/B testing, feedback loops, LLM cost routing)

## License

MIT
