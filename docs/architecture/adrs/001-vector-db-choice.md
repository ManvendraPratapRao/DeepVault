# ADR 001: Vector Database Selection

## Status
Accepted

## Context
As part of the DeepVault Enterprise Retrieval-Augmented Generation (RAG) platform, we require a system capable of storing high-dimensional embeddings efficiently and performing rapid K-Nearest Neighbor (K-NN) and Approximate Nearest Neighbor (ANN) searches. During Phase 1 engineering, we evaluated multiple database providers including FAISS, ChromaDB, Pinecone, and Qdrant. 

## Decision
We elected to natively integrate **Qdrant** as the primary vector database utilizing its "Local Path" storage engine for initial iterations, with seamless scalability to its Docker/Server engines.

## Rationale
1. **Zero External Dependencies**: By utilizing `qdrant-client`'s local storage engine, the system utilizes SQLite mapping under the hood. This elegantly avoids demanding users to establish complex container architectures just to execute minimal viable prototypes.
2. **Deterministic Scalability**: Qdrant natively offers zero-friction migration. Our code base transitions automatically from `path="qdrant_storage"` to `url="http://localhost:6333"` simply by toggling an `.env` variable without requiring refactored indexing logic.
3. **Rust-Based Performance**: Compared to Python-native clients like ChromaDB or non-persistent arrays like FAISS, Qdrant’s core Rust engine demonstrates categorically superior benchmark throughput natively, which is critical for scaling to 5,000+ synthesized datasets.

## Consequences
- **Positive**: Developers can locally clone and boot the enterprise framework without container orchestration overheads (`docker-compose`).
- **Positive**: We enforce a strong isolation gap between text storage (SQLite layer) and vector mapping.
- **Negative (Mitigated)**: Running Qdrant over the local path induces strict file-locks inside Python. We circumvented this by strategically configuring `seed_data.py` to target the active dynamic Docker HTTP endpoints rather than locking the localized disks simultaneously.
