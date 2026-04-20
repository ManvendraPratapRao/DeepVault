# DeepVault Architecture

DeepVault follows a **Hexagonal (Ports and Adapters)** architecture. Business logic depends only on abstract interfaces, and concrete implementations are injected at runtime.

## Layer Overview

| Layer | Path | Responsibility |
|-------|------|---------------|
| **API** | `app/api/` | HTTP routing, request validation, response serialization, middleware |
| **Services** | `app/services/` | Business logic orchestration (ingestion, query, document management) |
| **Core** | `app/core/` | Domain models, abstract interfaces (ABCs), custom exceptions |
| **Infrastructure** | `app/infrastructure/` | Concrete implementations (Qdrant, Groq, Redis, SQLite, BGE embedder) |
| **Prompts** | `app/prompts/` | Versioned prompt templates for RAG and evaluation |

## Component Diagram (Phase 2)

```mermaid
graph TD
    subgraph "API Layer (Ports)"
        FE[Streamlit UI] --> API[FastAPI /api/v1]
        API --> MW[Middleware: Logging + Rate Limiting]
    end

    subgraph "Service Layer (Orchestrators)"
        MW --> IS[Ingestion Service]
        MW --> QS[Query Service]
        MW --> DS[Document Service]
    end

    subgraph "Core Layer (Interfaces)"
        IS -.-> CH[BaseChunker]
        IS -.-> EM[BaseEmbedder]
        IS -.-> VS[BaseVectorStore]
        IS -.-> MS[BaseDocumentStore]
        QS -.-> RT[BaseRetriever]
        QS -.-> RNK[BaseReranker]
        QS -.-> RW[BaseQueryRewriter]
        QS -.-> LLM[BaseLLMClient]
        QS -.-> CS[CacheService]
    end

    subgraph "Infrastructure Layer (Adapters)"
        CH --> C1[FixedWindowChunker]
        CH --> C2[SlidingWindowChunker]
        CH --> C3[StructureChunker]
        CH --> C4[SemanticChunker]
        RT --> VR[VectorRetriever]
        RT --> BM25[BM25Retriever]
        RT --> HY[HybridRetriever ← VR + BM25]
        RNK --> CE[CrossEncoderReranker]
        RW --> GQR[GroqQueryRewriter]
        LLM --> GR[GroqLLMClient]
        EM --> BGE[BgeEmbedder]
        VS --> QD[(Qdrant)]
        MS --> SQL[(SQLite)]
        CS --> RD[(Redis)]
    end
```

## Data Flow

### Ingestion Pipeline
```
File/Text → Hash Check → Chunker → Embedder → Qdrant (vectors) + SQLite (metadata)
```
- The ingestion service first computes a SHA-256 hash of the content to detect duplicates.
- Chunking runs in a thread pool (`asyncio.to_thread`) to avoid blocking the event loop.
- Embeddings are computed in batch via the BGE model.
- Storage uses an inverted write strategy: vectors are written first, then metadata. If metadata storage fails, orphaned vectors are cleaned up from Qdrant.

### Query Pipeline (Phase 2)

**Strategy: `vector` (default)**
```
Question → [Cache Check] → [Query Rewriter?] → Embed Query → Qdrant Vector Search → Build Prompt → LLM → [Cache] → Return
```

**Strategy: `hybrid`**
```
Question → [Cache Check] → [Query Rewriter?] → Parallel(Vector Search, BM25 Search) → RRF Fusion → Build Prompt → LLM → [Cache] → Return
```

**Strategy: `hybrid_rerank`**
```
Question → [Cache Check] → [Query Rewriter?] → Parallel(Vector Search × 4, BM25 × 4) → RRF Fusion → CrossEncoder(top-20 → top-5) → Build Prompt → LLM → [Cache] → Return
```

- All strategies check the Redis cache first (hash-exact match).
- Query rewriting is opt-in per request via `use_query_rewriting=true`.
- Retrieved chunks include source filename and chunk index for citation.
- The LLM response includes token usage telemetry for cost tracking.

## Dependency Injection

All services receive their dependencies via constructor injection. The `app/dependencies.py` module acts as a service locator, building and caching singleton instances:

```python
async def get_query_service() -> QueryService:
    return QueryService(
        retriever=await get_retriever(),       # Vector, BM25, or Hybrid
        llm_client=await get_llm_client(),
        cache_service=await get_cache_service(),
        reranker=await get_reranker(),         # Only if hybrid_rerank
        rewriter=await get_query_rewriter(),
    )
```

This makes testing straightforward — each service can be instantiated with mock dependencies.

## Further Reading

- [Phase 2 Retrieval Architecture](architecture/phase2-retrieval-architecture.md)
- [ADR-006: BM25 Keyword Retrieval](adrs/006-bm25-keyword-retrieval.md)
- [ADR-007: RRF Fusion Strategy](adrs/007-rrf-fusion-strategy.md)
- [ADR-008: Cross-Encoder Reranker](adrs/008-cross-encoder-reranker.md)
- [Benchmark v2.0.0: Phase 2 Results](benchmarks/v2.0.0.md)

