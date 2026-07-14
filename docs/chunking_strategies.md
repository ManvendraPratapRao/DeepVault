# Chunking Strategies

DeepVault implements four text chunking strategies, each optimized for different document types. Every strategy implements the `BaseChunker` interface and writes to its own isolated Qdrant collection for fair benchmarking.

## Strategy Comparison

| Strategy | Best For | Speed | Faithfulness (V2) | Hallucination Rate |
|----------|---------|-------|-------------------|-------------------|
| **Sliding Window** 🏆 | General-purpose | Fast | 3.34 | 28.0% |
| Fixed Window | Baseline / control | Fastest | 3.22 | 34.0% |
| Structure | Markdown documents | Fast | 3.08 | 36.0% |
| Semantic | Dense technical prose | Slow (requires embedding) | 2.86 | 40.0% |

---

## 1. Fixed Window Chunker

**Path:** `app/infrastructure/chunkers/fixed.py`

Splits text into fixed-size character chunks with configurable overlap. The simplest and fastest strategy — serves as the baseline for comparison.

**How it works:**
1. Validates that `overlap < chunk_size` to prevent infinite loops.
2. If the document is shorter than `chunk_size`, returns a single chunk.
3. Slides a window forward by `chunk_size - overlap` characters each step.

**Parameters:** chunk_size=500, overlap=100 (20%)

**Trade-off:** Deterministic and fast, but can split sentences mid-word.

---

## 2. Sliding Window Chunker

**Path:** `app/infrastructure/chunkers/sliding.py`

An enhanced version of the fixed chunker that respects sentence boundaries. After the V2 refactor, this became our highest-performing strategy.

**How it works:**
1. Expands the window END up to 100 characters to find a sentence terminator (`.!?` followed by whitespace).
2. Aligns the window START at the nearest sentence boundary within the overlap zone.
3. This ensures both the start and end of each chunk fall on natural language boundaries.

**Parameters:** window_size=600, stride=480 (20% overlap)

**V2 Refactor:** The original implementation used a rigid mathematical stride for the start position, which could tear sentences in half. The fix searches for sentence boundaries near the target start point.

---

## 3. Structure Chunker

**Path:** `app/infrastructure/chunkers/structure.py`

Splits documents along Markdown heading boundaries (`#` through `######`). Each heading starts a new chunk, preserving the document's logical outline.

**How it works:**
1. Parses the text into `(heading, body)` pairs using regex.
2. If no headings are found (e.g., extracted PDF text), falls back entirely to `FixedWindowChunker`.
3. If a section exceeds `max_section_size`, sub-chunks the body using `FixedWindowChunker` and prepends the heading to each sub-chunk (with `(cont.)` suffix for continuation chunks).

**Parameters:** max_section_size=1500, fallback_chunk_size=500, fallback_overlap=100

**V2 Refactor:** The original implementation only attached the heading to the first sub-chunk. Subsequent sub-chunks lost their heading context, causing the LLM to hallucinate. The fix prepends the heading with `(cont.)` to all sub-chunks.

---

## 4. Semantic Chunker

**Path:** `app/infrastructure/chunkers/semantic.py`

The most computationally intensive strategy. Groups sentences by embedding similarity — when cosine similarity between consecutive sentences drops below a threshold, a new chunk begins.

**How it works:**
1. Splits the document into sentences using regex (`(?<=[.!?])\s+`).
2. Embeds all sentences using the BGE model (synchronous, runs inside `asyncio.to_thread`).
3. Computes cosine similarity between each pair of consecutive sentences.
4. When similarity drops below the threshold OR the current chunk exceeds `max_chunk_size`, starts a new chunk.
5. Bridges consecutive chunks by duplicating the last sentence of chunk A as the first sentence of chunk B.
6. Merges tiny chunks (below `min_chunk_size`) into their predecessor.

**Parameters:** similarity_threshold=0.85, min_chunk_size=100, max_chunk_size=1500

**V2 Refactor:** Added the overlap bridge and max_chunk_size cap. Without these, the semantic chunker produced chunks with no contextual overlap and unbounded sizes, leading to the highest hallucination rate.

---

## Choosing a Strategy

- **Default recommendation:** Sliding Window. Best overall faithfulness and efficiency.
- **Structured Markdown docs:** Structure chunker preserves heading hierarchy.
- **Dense research papers:** Semantic chunker keeps logical arguments together (but slower ingestion).
- **Benchmarking / ablation studies:** Fixed window provides a clean baseline.

All strategies can be selected via the `CHUNKER_STRATEGY` environment variable or passed per-request in the query API.

## Phase 3/4 Query Intelligence Note

With the introduction of the **QueryRouter** in Phase 3, the underlying chunking strategy is even more critical. 
- Factual queries routed to BM25 search heavily favor **Sliding Window** or **Fixed Window** chunking, as exact keywords are preserved.
- Semantic queries perform exceptionally well with the **Semantic** and **Structure** chunkers, as the logical boundaries of the text are maintained in the vector space.
- The `auto` retrieval strategy relies on a consistent chunking backbone (we recommend `sliding` as the default) to ensure cross-query robustness.
