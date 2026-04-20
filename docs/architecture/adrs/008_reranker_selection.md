# ADR-008: Cross-Encoder Model Selection

*   **Status**: Accepted
*   **Date**: 2026-04-14
*   **Decider**: Antigravity (AI Architect)

## Context and Problem Statement

Hybrid retrieval fetches a mix of semantic and keyword matches. To maximize precision, we need a high-accuracy "reranker" model that performs contextual scoring of the top candidates. This model must be efficient enough to run on standard CPU infrastructure without introducing prohibitive latency.

## Decision Drivers

1.  **Latency**: Reranking top-20 chunks should take less than 1-2 seconds.
2.  **Accuracy**: Must significantly outperform pure bi-encoders (like the BGE embedder) in determining passage relevance.
3.  **Footprint**: Small model size to minimize container image overhead.

## Considered Options

1.  **BAAI/bge-reranker-large**: State-of-the-art accuracy, but very slow (>5s on CPU) and high memory usage.
2.  **cross-encoder/ms-marco-MiniLM-L-6-v2**: Optimized for speed, specifically trained on MS-MARCO (Search relevance).
3.  **Cohere Rerank API**: Extremely accurate, but introduces external dependency, cost, and variable API latency.

## Decision Outcome

Chosen Option: **cross-encoder/ms-marco-MiniLM-L-6-v2**

### Reasons
-   **Industry Standard**: This model is the gold standard for "fast reranking" in open-source RAG.
-   **Size/Performance**: At ~90MB, it is lightweight. Scoring 20 candidates on a modern CPU (like this environment) takes ~1s.
-   **Domain Fit**: Trained specifically for the MS-MARCO search task, making it robust across scientific and synthetic contexts.

## Consequences

-   **Deployment**: Requires `sentence-transformers` and `torch`.
-   **Initialization**: The `RerankerService` implemented a "Lazy Load" pattern to ensure the model only takes up RAM when the `hybrid_rerank` strategy is explicitly requested, preserving system resources for simple vector search.
