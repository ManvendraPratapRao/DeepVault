# ADR 004: Interface-Driven Domain Driven Design

## Status
Accepted

## Context
RAG infrastructure is exceptionally fluid. Generative Models (OpenAI vs Groq), Vector Stores (Qdrant vs FAISS), and Chunkers dynamically evaluate differently based on rapidly shifting industry paradigms. Tightly coupling business logic directly against external provider classes (e.g. importing `AsyncQdrantClient` directly into the routing layer) guarantees devastating technical debt when migrations are inevitable. 

## Decision
We elected to strictly map out **Interface-Driven Design** across `app/core/interfaces`, dictating exact `abc.ABC` abstract classes enforcing concrete implementation typing bounds universally across the pipeline.

## Rationale
1. **Testing Scalability**: Constructing `ABC` networks allows explicit Mock derivations utilizing `unittest.mock.AsyncMock`. Without interfaces enforcing types mechanically, automated integration tests inherently break silently.
2. **Dynamic Overrides**: Utilizing `FastAPI Dependencies`, the architecture dynamically overrides the concrete classes natively depending on external bounds (e.g., executing `BaseVectorStore` and dynamically routing the pipeline to `SQLite`, `Qdrant`, or Mock arrays depending literally on the `.env` settings map seamlessly).
3. **Clean Architecture Isolation**: Service layers (`QueryService`, `IngestionService`) organically rely perfectly on abstracted `Chunk` objects natively, ignoring network overhead completely computationally. 

## Consequences
- **Positive**: We completely decoupled business logic from operational implementations natively. 
- **Negative (Mitigated)**: Development incurs slight boiler-plate overheads manually engineering robust interfaces instead of rapid-prototyping scripts directly. We accept this immediately to guarantee long-term system integrity dynamically via `.py` structures.
