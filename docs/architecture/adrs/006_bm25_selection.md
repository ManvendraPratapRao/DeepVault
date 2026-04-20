# ADR-006: BM25 (Rank-BM25) vs. Elasticsearch/OpenSearch

*   **Status**: Accepted
*   **Date**: 2026-04-14
*   **Decider**: Antigravity (AI Architect)

## Context and Problem Statement

For Phase 2 of DeepVault, we needed a robust keyword-based search engine to complement our Vector (Semantic) retrieval. The requirement was to provide high-recall keyword matching for exact terms, unique identifiers, and abbreviations that vector embeddings often fail to capture.

## Decision Drivers

1.  **Deployment Complexity**: Elasticsearch and OpenSearch require dedicated Java-based containers, significant RAM (minimum 2-4GB), and complex cluster management.
2.  **Latency**: For small-to-mid-sized collections (1k-1M chunks), a Python-native implementation can load and query indices faster than cross-service REST calls.
3.  **Cost**: Managed Elasticsearch instances (e.g., AWS OpenSearch) are expensive portfolio-wise.
4.  **Integration**: The solution must integrate seamlessly with our existing Qdrant-based chunk storage.

## Considered Options

1.  **Elasticsearch**: Industry standard but heavy.
2.  **Rank-BM25 (Python)**: Implementation of BM25Okapi in pure Python.
3.  **Tantivy (Rust)**: High performance but harder to customize in Python.

## Decision Outcome

Chosen Option: **Rank-BM25**

### Reasons
1.  **Zero-Infrastructure**: No additional Docker containers are required. The index is built in-memory on startup from Qdrant payloads.
2.  **Developer Experience**: Simple API that maps directly to our `BaseRetriever` interface.
3.  **Performance**: Querying a 100k chunk index takes <10ms in Python, making it a perfect candidate for Hybrid RRF merging.

## Consequences

-   **Memory Usage**: The BM25 index stays in RAM. For extremely large datasets (1M+ chunks), we may need to migrate to a disk-based solution like Tantivy or Elasticsearch in Phase 3.
-   **Startup Time**: The service must "warm up" by scrolling chunks from Qdrant to build the initial BM25 index.
