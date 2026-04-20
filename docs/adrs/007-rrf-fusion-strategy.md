# ADR-007: Hybrid Fusion Strategy — Reciprocal Rank Fusion (RRF)

**Status:** Accepted  
**Date:** 2026-04-14  
**Author:** Manvendra Pratap Rao

---

## Context

`HybridRetriever` must merge results from two independent retrievers — dense vector search (semantic) and BM25 (keyword) — into a single ranked list. Each retriever returns items in a ranked order with different, incomparable score scales:

- **Vector search** returns cosine similarity scores in `[0, 1]`.
- **BM25** returns raw TF-IDF-based scores in `[0, ∞)`, varying by document length and corpus statistics.

These scores cannot be directly compared or averaged. A merging strategy is needed that is:
- **Score-independent**: Does not assume the scores are on the same scale.
- **Robust to outliers**: A single very high BM25 score shouldn't dominate.
- **Configurable weighting**: Vector-heavy for semantic queries, BM25-heavy for keyword queries.
- **Simple to implement and reason about**.

Candidates: **Reciprocal Rank Fusion (RRF)**, **Weighted Score Normalization (linear combination)**, **Borda Count**, **CombSUM/CombMNZ**.

---

## Decision

**Use Reciprocal Rank Fusion (RRF)** as the merging strategy in `HybridRetriever`.

---

## The RRF Formula

For each retriever result list, each document `d` at rank `r` receives:

```
score(d) += weight × (1 / (k + r))
```

Where:
- `k = 60` (smoothing constant, standard value from Cormack et al., 2009)
- `r` is the 0-indexed rank of the document in the retriever's result list
- `weight` is the retriever's weight (default: 0.5 for each)

Final documents are ranked by their summed RRF score.

---

## Evaluation

### Reciprocal Rank Fusion (RRF)

| Criterion | Assessment |
|-----------|------------|
| Score independence | ✅ Uses only rank position, ignores raw scores entirely. |
| Robustness | ✅ The `k + r` denominator diminishes the advantage of top-ranked items gracefully. |
| Well-studied | ✅ Original paper: Cormack, Clarke, Buettcher (SIGIR 2009). Used in production at major search companies. |
| Configurable | ✅ Per-retriever weights allow tuning (e.g., alpha=0.7 vector, beta=0.3 BM25 for semantic-heavy queries). |
| Implementation complexity | ✅ 20 lines of Python. |

### Weighted Score Normalization (Linear Combination)

```
final_score(d) = alpha × normalize(vector_score) + beta × normalize(bm25_score)
```

| Criterion | Assessment |
|-----------|------------|
| Score normalization | ❌ Requires min-max normalization per retriever per query — sensitive to outliers. |
| Robustness | ❌ A single document with a very high BM25 raw score distorts the normalized range. |
| Tuning | ⚠️ Requires empirical tuning of `alpha` and `beta` per corpus. |

**Rejected:** Score normalization is fragile. BM25 scores vary dramatically by document length and corpus vocabulary, making stable normalization difficult without extensive per-corpus calibration.

### Borda Count

Each document at rank `r` in a list of `N` results receives `N - r` points.

| Criterion | Assessment |
|-----------|------------|
| Score independence | ✅ Rank-based. |
| Robustness | ⚠️ Sensitive to `N` — the total number of candidates retrieved. |
| Configurable weighting | ❌ Not naturally weighted. |

**Rejected:** Less flexible than RRF for weighted combination.

### CombSUM / CombMNZ

Classic TREC-era fusion methods that combine and amplify scores.

| Criterion | Assessment |
|-----------|------------|
| Score independence | ❌ Still requires scores on comparable scales. |
| Adoption | ⚠️ Less widely used in modern RAG literature. |

**Rejected:** Score-scale dependency makes them unsuitable here.

---

## Parameter Choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `rrf_k` | 60 | Standard value from Cormack et al. (2009). Tested on TREC datasets. |
| `vector_weight` | 0.5 | Equal weighting by default. Tune per deployment via `HybridRetriever(vector_weight=X)`. |
| `bm25_weight` | 0.5 | Equal weighting by default. |
| `fetch_k` | `top_k × 4` | Fetch 4× candidates from each retriever before fusion to maximize overlap surface. |

---

## Consequences

**Positive:**
- Completely score-scale independent — works regardless of how BM25 or vector scores are distributed.
- Documents appearing in *both* result lists receive a higher combined score — rewards consensus.
- Simple, auditable code. The entire fusion logic is ~15 lines.
- Weighted variants allow per-query tuning.

**Negative:**
- Ignores raw score magnitudes — a document with 0.99 cosine similarity is treated the same as 0.61 at the same rank position.
- If one retriever returns very few results (e.g., BM25 with no matching keywords), fusion is dominated by the other retriever.

---

## Implementation Notes

- Location: `app/infrastructure/retrievers/hybrid.py`.
- Both retrievers are called in parallel via `asyncio.gather()` — no sequential blocking.
- `HybridRetriever` itself implements `BaseRetriever`, making it composable with any future retriever.
- The reranker (`CrossEncoderReranker`) is applied *after* RRF fusion when `retrieval_strategy = "hybrid_rerank"`.
