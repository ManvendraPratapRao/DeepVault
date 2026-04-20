# ADR-004: Interface-Driven Design — Abstract Base Classes for All Components

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Manvendra Pratap Rao

---

## Context

DeepVault is designed as a comparative benchmarking platform as much as an operational RAG system. Its core requirement is the ability to **swap** components (chunkers, retrievers, embedders, LLM providers, vector stores) without rewriting business logic. This creates a direct need for a strong interface contract.

Without strict interfaces:
- `QueryService` would have to know whether it's using Qdrant or FAISS, Groq or OpenAI.
- Adding a new chunker would require modifying `IngestionService`.
- Unit tests would require spinning up real infrastructure instead of using mocks.
- Phase 2's hybrid retriever (which composes two retrievers) would be impossible to implement cleanly.

---

## Decision

**Define Abstract Base Classes (ABCs) in `app/core/interfaces/` for every swappable component.** All infrastructure implementations must inherit from the corresponding ABC. All service-layer code depends only on ABCs, never on concrete implementations.

---

## Interfaces Defined

| Interface | Location | Implementations |
|-----------|----------|----------------|
| `BaseChunker` | `app/core/interfaces/chunker.py` | `FixedWindowChunker`, `SlidingWindowChunker`, `StructureChunker`, `SemanticChunker` |
| `BaseEmbedder` | `app/core/interfaces/embedder.py` | `BgeEmbedder` |
| `BaseVectorStore` | `app/core/interfaces/vector_store.py` | `QdrantVectorStore` |
| `BaseDocumentStore` | `app/core/interfaces/document_store.py` | `SqliteDocumentStore` |
| `BaseLLMClient` | `app/core/interfaces/llm_client.py` | `GroqLLMClient` |
| `BaseRetriever` | `app/core/interfaces/retriever.py` | `VectorRetriever`, `BM25Retriever`, `HybridRetriever` |
| `BaseReranker` | `app/core/interfaces/reranker.py` | `CrossEncoderReranker` |
| `BaseQueryRewriter` | `app/core/interfaces/rewriter.py` | `GroqQueryRewriter` |

---

## Design Principles

### 1. Depend on Abstractions, Not Concretions

```python
# ✅ Service layer depends on BaseRetriever
class QueryService:
    def __init__(self, retriever: BaseRetriever, ...):
        self.retriever = retriever

# ❌ Service layer should NOT do this
class QueryService:
    def __init__(self, retriever: VectorRetriever, ...):
        self.retriever = retriever
```

### 2. Constructor Injection (not service locator inside services)

All dependencies are passed into service constructors. The `app/dependencies.py` module is the single place responsible for resolving the concrete type and constructing the dependency graph.

### 3. ABCs Enforce the Contract with `@abstractmethod`

Each ABC uses Python's `abc.ABC` and `@abstractmethod` to ensure that any class that inherits the interface must implement all required methods. Missing implementations raise `TypeError` at import time, not at runtime.

### 4. Strategy Pattern for Phase 2

The `BaseRetriever` interface makes Phase 2's `HybridRetriever` elegant:

```python
class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        vector_retriever: BaseRetriever,  # Takes ANY retriever
        bm25_retriever: BaseRetriever,    # Takes ANY retriever
    ): ...
```

This means HybridRetriever can compose any two retrievers. It doesn't know or care about Qdrant or BM25 internals.

---

## Alternatives Considered

### Protocol Classes (PEP 544 — Structural Subtyping)

Python's `typing.Protocol` allows duck-typing without inheritance. Classes that satisfy the protocol's structure are automatically compatible.

**Rejected:** Protocols don't enforce the contract at definition time. A class can "accidentally" satisfy a protocol without intent. ABCs make the relationship explicit and enforce it via `@abstractmethod`. For a system with 8 swappable interfaces, explicit is better than implicit.

### Dataclasses / TypedDicts

Not applicable — the interfaces define *behavior* (methods), not *data structure*.

---

## Consequences

**Positive:**
- Adding a new chunker or retriever requires zero changes to `IngestionService` or `QueryService`.
- Unit tests mock the ABCs directly without needing live infrastructure.
- Phase 2's `HybridRetriever` composes two `BaseRetriever` instances cleanly.
- Type checkers and IDEs surface incorrect usage at development time.
- Future Phase 4 migration (SQLite → PostgreSQL) requires creating one new class, not modifying any existing service.

**Negative:**
- More boilerplate than a direct implementation. Each component requires an ABC + concrete class.
- Adds a layer of indirection that can make tracing execution harder for newcomers.

---

## Implementation Notes

- ABCs are in `app/core/interfaces/`. The `__init__.py` exports all ABCs for clean imports.
- Concrete implementations are in `app/infrastructure/`.
- The dependency graph is assembled in `app/dependencies.py`, which is the only file that imports concrete implementations directly.
