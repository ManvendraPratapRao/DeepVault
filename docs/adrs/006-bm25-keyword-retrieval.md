# ADR-006: Keyword Retrieval — BM25 over Elasticsearch

**Status:** Accepted  
**Date:** 2026-04-14  
**Author:** Manvendra Pratap Rao

---

## Context

Phase 2 introduces **keyword-based retrieval** to complement the existing dense vector search. Vector search excels at semantic similarity ("what are the risks of this approach?") but struggles with exact keyword matching ("what is the definition of HNSW?" or "find documents mentioning ISO 27001").

The requirement is a retrieval component that:
- Ranks documents by exact term frequency and inverse document frequency (TF-IDF family).
- Can be bootstrapped from the existing Qdrant collection at startup without a separate data pipeline.
- Works without an external service (no Elasticsearch, no Solr server).
- Integrates with the `BaseRetriever` ABC so it can be composed into `HybridRetriever`.
- Handles multiple isolated collections (one per chunking strategy), matching Qdrant's collection-per-strategy model.

Candidates: **rank-bm25 (in-process BM25)**, **Elasticsearch**, **Typesense**, **Qdrant built-in sparse vectors**.

---

## Decision

**Use `rank-bm25` (BM25Okapi)** implemented as an in-process index bootstrapped from Qdrant payloads at startup.

---

## Evaluation

### rank-bm25 (in-process BM25Okapi)

| Criterion | Assessment |
|-----------|------------|
| External service | ✅ None. Pure Python, runs in-process. |
| Bootstrap from Qdrant | ✅ Uses Qdrant's scroll API to load all chunk payloads at startup. |
| Multiple collections | ✅ Maintains one `BM25Okapi` index per collection key (`dict[str, BM25Okapi]`). |
| Latency | ✅ In-process. Sub-millisecond for corpus <100K documents. |
| `BaseRetriever` compatibility | ✅ `BM25Retriever` implements `BaseRetriever.retrieve()` directly. |
| Accuracy | ✅ BM25Okapi is the standard probabilistic retrieval model (Robertson & Zaragoza, 2009). |
| Memory overhead | ⚠️ Full corpus stored in memory. Acceptable for Phase 1-2 corpus (~10K chunks). |
| Index freshness | ⚠️ In-memory index; stale after re-ingestion (requires restart or re-initialization). |

### Elasticsearch

| Criterion | Assessment |
|-----------|------------|
| External service | ❌ Requires a running Elasticsearch cluster (Docker or managed). |
| Operational overhead | ❌ JVM-based. 512MB–2GB RAM just for the server. |
| Setup complexity | ❌ Requires mapping definition, index templates, and a synchronization pipeline from Qdrant. |
| Accuracy | ✅ BM25 + vector hybrid natively supported (Elasticsearch 8+). |
| Portfolio signal | ⚠️ Knowing Elasticsearch is valuable, but it's disproportionate infrastructure for this corpus size. |

**Rejected:** Adds significant infrastructure complexity for a corpus that fits comfortably in memory. The operational overhead is not justified at Phase 1-2 scale. If the corpus grows to millions of documents, Elasticsearch is the right answer. That migration path is preserved by the `BaseRetriever` ABC — swapping is one new class.

### Typesense

| Criterion | Assessment |
|-----------|------------|
| External service | ❌ Requires a Typesense server. |
| BM25 quality | ✅ Uses BM25 ranking. |
| Sync pipeline | ❌ Same data synchronization challenge as Elasticsearch. |

**Rejected:** Same infrastructure objection as Elasticsearch.

### Qdrant Sparse Vectors (SPLADE / Term-Frequency Sparse)

| Criterion | Assessment |
|-----------|------------|
| External service | ✅ Uses existing Qdrant. |
| Implementation | ⚠️ Requires sparse vector model (SPLADE, BM42). Not a pure BM25. |
| Complexity | ⚠️ Requires re-ingesting all documents with sparse vectors, changing the ingestion pipeline. |
| Phase 2 scope | ❌ Out of scope for Phase 2. |

**Deferred to Phase 3+:** SPLADE/sparse vector hybrid inside Qdrant is a compelling future improvement, but it requires a data migration and a new model dependency.

---

## Implementation Design

```
Application startup
    └── BM25Retriever.initialize(collection_name)
            └── Qdrant scroll (all chunks)
            └── tokenize(content) → word list per chunk
            └── BM25Okapi(tokenized_corpus)
            └── cache in _indexes[collection_name]

Query time
    └── BM25Retriever.retrieve(query, top_k, collection_name)
            └── tokenize(query)
            └── BM25Okapi.get_top_n(query_tokens, corpus, n=top_k)
            └── return list[Chunk]
```

**Double-checked locking:** `asyncio.Lock` prevents multiple concurrent callers from building the same index simultaneously.

---

## Consequences

**Positive:**
- Zero additional infrastructure. Works without any new Docker services.
- BM25 dramatically improves recall for exact-keyword queries (product names, acronyms, API names, ISO standards).
- Composable with `HybridRetriever` via the `BaseRetriever` interface.

**Negative:**
- Index is stale after re-ingestion. Must call `initialize()` again or restart.
- Memory scales with corpus size (estimated ~50MB for 50K chunks).
- No persistence — index rebuilds on every startup (~2-5 seconds for 10K chunks).
- Does not support fuzzy matching or stemming by default (basic whitespace tokenization).

---

## Implementation Notes

- Location: `app/infrastructure/retrievers/bm25.py`.
- Tokenizer: `re.sub(r"[^\w\s]", "", text.lower()).split()` — lowercased words, punctuation stripped.
- Index initialized lazily on first retrieval call for a given collection.
- Singleton managed by `app/dependencies.py` (`get_bm25_retriever()`).
