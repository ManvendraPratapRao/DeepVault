# ADR-008: Reranker Model — ms-marco-MiniLM-L-6-v2 Cross-Encoder

**Status:** Accepted  
**Date:** 2026-04-14  
**Author:** Manvendra Pratap Rao

---

## Context

After `HybridRetriever` fuses vector and BM25 results (via RRF), the `hybrid_rerank` strategy applies a **cross-encoder reranker** to re-score the top-N candidate chunks before returning the final top-K to the LLM.

A bi-encoder (like the BGE embedder) encodes query and document *separately* and computes similarity as a dot product. This is fast but loses the fine-grained interaction between query and document tokens.

A **cross-encoder** reads both the query and document *simultaneously* through its full self-attention stack, capturing token-level interactions (e.g., understanding that "bank" in the query refers to "financial institution" not "river bank" based on the document context). This produces significantly better relevance scores at the cost of higher latency.

The reranker is applied at the end of the pipeline: retrieve 20 candidates → rerank → return top 5.

---

## Decision

**Use `cross-encoder/ms-marco-MiniLM-L-6-v2`** from `sentence-transformers` as the cross-encoder reranker.

---

## Model Candidates Evaluated

### ms-marco-MiniLM-L-6-v2 (Selected)

| Criterion | Assessment |
|-----------|------------|
| Model size | ✅ ~22MB. Fast to load and run. |
| CPU inference | ✅ Runs comfortably on CPU. p50 latency: ~80-150ms for 20 pairs. |
| Quality | ✅ Trained on the MS MARCO passage retrieval dataset (530K passages). State-of-the-art for its size category. |
| Framework | ✅ Available via `sentence-transformers`. `CrossEncoder` class handles tokenization. |
| Async safety | ✅ Inference offloaded to `asyncio.to_thread` — does not block the event loop. |
| License | ✅ Apache 2.0. |
| Benchmark score | ✅ MRR@10: 0.334 on MS MARCO dev set (source: SBERT.net leaderboard). |

### ms-marco-MiniLM-L-12-v2 (Larger sibling)

| Criterion | Assessment |
|-----------|------------|
| Quality | ✅ Slightly better MRR@10 (0.347). |
| Speed | ⚠️ 2× the parameters (~44MB). p50 latency increases to ~200-300ms. |
| Tradeoff | ⚠️ ~4% quality gain for ~100% latency increase. |

**Not selected:** The L-6 variant already provides a meaningful quality lift from RRF alone. The latency cost of L-12 is not justified for Phase 2.

### cross-encoder/ms-marco-electra-base

| Criterion | Assessment |
|-----------|------------|
| Quality | ✅ Higher accuracy than MiniLM. |
| Speed | ❌ Much larger model. Not practical on CPU. |

**Rejected:** Too slow for CPU-bound development environments.

### BAAI/bge-reranker-base

| Criterion | Assessment |
|-----------|------------|
| Quality | ✅ Competitive with ms-marco-MiniLM. |
| Framework | ⚠️ Requires different loading code than `sentence-transformers CrossEncoder`. |
| MS MARCO training | ⚠️ Primarily trained on Chinese/multilingual data with English MS MARCO fine-tuning. |

**Not selected:** Less standard for English-language MS MARCO passage retrieval. ms-marco-MiniLM has more published benchmarks.

---

## Integration Pattern

```
hybrid_rerank strategy pipeline:
    1. HybridRetriever.retrieve(query, top_k=20)  ← over-fetch 4× candidates
    2. CrossEncoderReranker.rerank(query, chunks, top_k=5)  ← re-score and prune
    3. LLM.generate(query, top_5_chunks)  ← final answer generation
```

The reranker receives the query and each candidate chunk as a `(query, chunk_text)` pair. The cross-encoder scores each pair independently. Pairs are then sorted by score descending and truncated to `top_k`.

---

## Async Safety

Cross-encoder inference is synchronous (`model.predict(pairs)`). To prevent blocking FastAPI's async event loop during inference:

```python
scores = await asyncio.to_thread(self.encoder.predict, pairs)
```

This offloads the CPU-bound inference to a thread pool, keeping the event loop free for other requests.

---

## Fail-Open Design

If reranking fails (model load error, unexpected input shape, memory error), the reranker falls back to returning the original retriever-ordered chunks truncated to `top_k`:

```python
except Exception as e:
    logger.error(f"Cross-Encoder reranking failed: {e}")
    return chunks[:top_k]  # fail-open: return upstream ranked results
```

---

## Consequences

**Positive:**
- Cross-encoder re-ranks with full query-document attention, correcting BM25/vector ranking errors.
- MiniLM-L-6 is fast enough for synchronous inference with `asyncio.to_thread`.
- Fail-open design ensures `hybrid_rerank` gracefully degrades to `hybrid` if the model fails.
- Apache 2.0 license — no restrictions on commercial use.

**Negative:**
- Adds a model load time at startup (~1-2 seconds on first call).
- CPU inference latency adds ~100-200ms to `hybrid_rerank` queries vs `hybrid`.
- The model is downloaded from HuggingFace on first use (~22MB).
- Maximum safe input size is 100 pairs before memory becomes a risk (enforced in code: `chunks = chunks[:100]`).

---

## Benchmark Impact

From `run_20260414_095030` (see `docs/benchmarks/v2.0.0.md`), for the **Fixed** chunking strategy:

| Strategy | Faithfulness | Hallucination Rate | Context Precision @1 |
|----------|-----------|--------------------|---------------------|
| vector | 3.196 | 37.5% | 71.4% |
| hybrid | **3.304** | **28.6%** | 71.4% |
| hybrid_rerank | 3.018 | 41.1% | 71.4% |

The reranker showed mixed results — improving some metrics for some chunking strategies while slightly degrading others. This is expected: reranking helps most when initial retrieval quality is low and when queries are longer/more complex. Detailed per-strategy analysis is in `docs/benchmarks/v2.0.0.md`.

---

## Implementation Notes

- Location: `app/infrastructure/rerankers/cross_encoder.py`.
- Model name configurable at instantiation: `CrossEncoderReranker(model_name="...")`.
- Singleton managed by `app/dependencies.py` (`get_reranker()`).
- Only instantiated when `RETRIEVAL_STRATEGY = "hybrid_rerank"` to save memory for vector-only users.
