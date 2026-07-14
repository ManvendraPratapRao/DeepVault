# DeepVault — Enterprise RAG Platform

DeepVault is a production-grade Retrieval-Augmented Generation (RAG) system built from scratch using interface-driven design. It ingests enterprise documents (Markdown, text, PDF), chunks them using **4 configurable strategies**, retrieves context via **6 retrieval pipelines** (including BM25 hybrid + cross-encoder reranking), and generates grounded answers using Groq's Llama-3 models.

It features an intelligent Query Router to dynamically select the best retrieval path based on the user's intent, and a Query Decomposer to handle complex, multi-part questions automatically. DeepVault is built for observability with Langfuse tracing (planned) and robust streaming interfaces.

## Why DeepVault?

We built DeepVault because standard RAG tutorials stop at "chunk text, put in vector DB, query LLM". Real enterprise systems fail doing this because:
1. **Not all queries are semantic searches.** Asking "What is X vs Y?" requires a different retrieval strategy than "Who is the CEO?".
2. **Confident Hallucinations.** If a user asks a question missing from the knowledge base, a basic RAG will confidently guess based on pre-training. DeepVault uses a Context Confidence Guard to refuse answering if the retrieved chunks score below a safety threshold.
3. **Black-box evaluation.** You can't improve what you don't measure. DeepVault provides a modular evaluation engine to benchmark faithfulness, hallucination rates, and cost-efficiency.

## Key Features

- **Query Intelligence Engine** 🧠
  - **Query Router**: Classifies incoming queries (factual, semantic, comparison, complex) and routes them to the optimal retrieval strategy with zero latency overhead.
  - **Query Decomposer**: Breaks complex multi-part questions into 2-4 focused sub-queries, retrieving in parallel and deduplicating results.
  - **LLM Router**: Cost-efficiently routes factual/simple queries to Llama-3.1-8b, and complex/semantic queries to Llama-3.3-70b.
- **4 Chunking Strategies** — Sliding window, recursive character, structure-based (Markdown headings), and semantic (embedding similarity). Each strategy creates an isolated Qdrant collection for side-by-side benchmarking.
- **6 Retrieval Pipelines** — Vector-only, BM25-only, Hybrid (BM25 + Vector via Reciprocal Rank Fusion), Hybrid + Cross-Encoder Reranking, and query-rewritten variants.
- **SSE Streaming** — Token-by-token response streaming via Server-Sent Events (`POST /api/v1/stream`) with UI integration.
- **Observability** — Transitioning to Langfuse (v2 Lite) for full LLM trace visibility and token cost tracking.
- **Redis Caching** — Semantic query cache and embedding cache. Feature-flag controlled.
- **Evaluation Engine** — Benchmark pipeline to measure Hit Rate, Faithfulness, and Hallucination rates across strategy combinations.
- **Rate Limiting** — Per-API-key sliding window rate limiter backed by Redis.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **API Framework** | FastAPI (Python 3.13) via [uv](https://github.com/astral-sh/uv) |
| **LLM Inference** | Groq (Llama-3.1-8b-instant & Llama-3.3-70b-versatile) |
| **Vector Database** | Qdrant (local or Docker) |
| **Embedding Model** | BAAI/bge-small-en-v1.5 (384-dim, runs on CPU) |
| **Metadata Store** | SQLite (async via aiosqlite) |
| **Caching** | Redis 7 |
| **Containerization** | Docker + Docker Compose |
| **Observability** | Langfuse v2 Lite (Planned) |

## System Architecture

DeepVault follows a **Hexagonal (Ports and Adapters)** architecture. Business logic depends only on abstract interfaces (`app/core/interfaces/`), making it straightforward to swap implementations (e.g., replacing Qdrant with Pinecone) without touching the core query pipeline.

For a detailed view of the architecture and data flows, see [docs/architecture.md](docs/architecture.md) and [docs/query_pipeline.md](docs/query_pipeline.md).

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
uv sync
```

### 2. Configure Environment
```bash
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
```

### 3. Start Infrastructure (Redis + Qdrant)
```bash
docker compose -f docker/docker-compose.yml up -d
```

### 4. Start the API
```bash
make dev
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 5. Launch the Dashboard
```bash
make ui
# Opens Streamlit at http://localhost:8501
```

## Documentation Map

If you want to understand the "whys" of this codebase, check out these guides:

- **[Architecture & Design](docs/architecture.md)** — Explains the Hexagonal architecture, Dependency Injection container, and overall layout.
- **[The Query Pipeline](docs/query_pipeline.md)** — A detailed walkthrough of what happens when a query hits the API, from classification to generation.
- **[Chunking Strategies](docs/chunking_strategies.md)** — Deep dive into the 4 chunking algorithms, their trade-offs, and when to use them.
- **[API Reference](docs/api_reference.md)** — Details on request/response schemas, endpoints, and authentication.
- **[Evaluation Engine](docs/eval.md)** — How we run automated benchmarks to prove our RAG is actually good.
- **[Deployment](docs/deployment.md)** — How to run this in production (Docker, caching, environment variables).
- **[Contributing](docs/contributing.md)** — Setup, test strategy, and conventions.

## License

MIT
