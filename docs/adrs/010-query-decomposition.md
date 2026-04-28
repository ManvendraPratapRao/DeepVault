# ADR-010: Query Decomposition for Complex Multi-Part Questions

**Status:** Accepted  
**Date:** 2026-04-28  
**Author:** Manvendra Pratap Rao

---

## Context

Complex multi-part questions frequently cause RAG systems to fail in a specific way: a single retrieval pass optimizes for the **most prominent** information need in the query and misses chunks relevant to secondary aspects.

Example failure:
> "What are the trade-offs of BM25 vs vector search and when should I use reranking?"

A single vector retrieval for this query may return chunks about BM25 trade-offs but completely miss chunks about reranking use cases. The LLM then generates speculative content for the second part — causing hallucination.

**Root cause:** Single retrieval passes treat multi-part queries as a single information need. The embedding of the full query is a mixture of both aspects, which dilutes the search signal.

**Requirement:** A mechanism to decompose complex queries into focused sub-queries and retrieve context for each independently.

---

## Decision

**Implement an LLM-based `QueryDecomposer`** that:
1. Calls Groq with a structured decomposition prompt to split the query into 2–4 sub-queries.
2. Executes sub-query retrievals **in parallel** via `asyncio.gather()`.
3. Merges and deduplicates results by chunk ID (preserving first-occurrence order).
4. Falls back to the original query on LLM failure (fail-open).

Decomposition is only activated for `complex` query type (as classified by `QueryClassifier`) to avoid unnecessary LLM calls for simple queries.

---

## Evaluation of Decomposition Approaches

### LLM-Based Decomposition (selected) ✅

| Criterion | Assessment |
|-----------|------------|
| Decomposition quality | ✅ LLM produces semantically coherent sub-queries |
| Latency overhead | ⚠️ +400–800ms for decomposition call (amortized by parallel retrieval) |
| Reliability | ✅ Fail-open design returns original query on any error |
| Cost | ⚠️ One additional Groq call per complex query |
| Control | ✅ Prompt-controlled — number of sub-queries capped at 4 |

### Rule-Based Decomposition (splitting on "and", "also", etc.)

| Criterion | Assessment |
|-----------|------------|
| Latency | ✅ Zero overhead |
| Quality | ❌ Naive splitting produces grammatically broken sub-queries |
| Accuracy | ❌ Cannot identify semantic boundaries in natural language |

**Rejected:** Rule-based splitting produces nonsensical sub-queries that confuse retrieval.

### Semantic Chunking of the Query (no decomposition)

Treating the full complex query as-is with `hybrid_rerank` retrieval (more candidates + reranker).

| Criterion | Assessment |
|-----------|------------|
| Simplicity | ✅ No additional LLM call |
| Multi-aspect coverage | ❌ Reranker prioritizes one aspect over the other |

**Partially adopted:** `hybrid_rerank` is used for complex queries **in addition to** decomposition when decomposition is enabled. When the LLM decomposition fails, the system falls back to this pattern.

---

## Implementation Design

```
User Query (complex)
    └── QueryDecomposer.decompose(query)
            └── LLM call (Groq, decomposition prompt)
            └── parse sub-queries (one per line)
            └── return [sub_q1, sub_q2, sub_q3]

                ┌──────────────────────────────────────┐
                │  asyncio.gather()                    │
                │  retrieve(sub_q1, top_k=fetch_k)     │
                │  retrieve(sub_q2, top_k=fetch_k)     │
                │  retrieve(sub_q3, top_k=fetch_k)     │
                └──────────────────────────────────────┘
                        │
                    deduplicate by chunk.id
                    (preserve first-occurrence order)
                        │
                    merged_chunks → LLM generation
```

**Parallelism benefit:** For N sub-queries, total retrieval latency ≈ `single_retrieval_latency` (not N × single_retrieval_latency) since all sub-queries execute concurrently.

---

## Prompt Design (`app/prompts/v3/decomposition.py`)

The decomposition prompt enforces:
- **One sub-question per line** — parseable without brittle JSON extraction.
- **No numbering or labels** — avoids the LLM adding "1.", "Sub-query:", etc.
- **Maximum 4 sub-questions** — prevents runaway decomposition.
- **Identity for simple queries** — if the query is already focused, output it unchanged.

A worked example is included in the system prompt to anchor the format.

---

## Deduplication Strategy

Sub-queries for different aspects of the same topic often retrieve overlapping chunks (especially the top-ranked ones). Without deduplication:
- The LLM receives the same chunk content multiple times.
- Context window is wasted.
- Prompt token count spikes unnecessarily.

**Strategy:** Deduplicate by `chunk.id` (UUID), preserving first-occurrence order. This is O(n) with a set and is stable (doesn't reorder chunks from the first sub-query).

---

## Consequences

**Positive:**
- Dramatically improves answer quality for multi-part questions by ensuring context for each aspect is retrieved.
- Parallel retrieval means minimal latency penalty for decomposition.
- Fail-open: users never see degraded behaviour due to decomposition errors.
- Clean prompt template with worked example makes LLM output consistent.

**Negative:**
- One additional Groq API call per complex query (adds ~400–800ms and minor cost).
- The decomposition LLM call is not cached (future improvement: cache by query hash).
- Deduplication by `chunk.id` preserves first-sub-query ordering, which may not always be optimal.
- Only activated for queries classified as `complex` — mismatch in classification = missed decomposition.

---

## Implementation Notes

- Location: `app/infrastructure/query/decomposer.py`
- Prompt: `app/prompts/v3/decomposition.py`
- Only runs when `query_type == "complex"` AND `QueryService.decomposer is not None`
- Min sub-query length: 8 chars (filters noise lines)
- Max sub-queries: 4 (hard-capped in parser)
- DI factory: `get_query_decomposer()` in `app/dependencies.py`
