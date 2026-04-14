# Case Study: DeepVault RAG - Post-Refactor V2 Benchmark

## 1. Executive Summary
Following the initial V1 deep-dive into DeepVault's ingestion strategies, we observed that advanced context-aware chunking methods (Semantic, Structure, Sliding) were underperforming against the naïve "Fixed" chunker. Our initial hypothesis was confirmed: the "advanced" logic was shearing context inappropriately at the boundaries, destroying the LLM's (Llama-3.1-8b) ability to ground itself.

We implemented targeted architectural refactors to the chunking algorithms to stitch context safely across boundaries. Upon reseeding the database and running a fresh Golden QA Evaluation set, the **Sliding Window** strategy overtook all others, jumping from #3 to the **#1 most efficient and faithful strategy** in the pipeline.

This new baseline validates our context-first ingestion philosophy and establishes a high-water mark for future retrieval experiments (like Hybrid Search & Reranking).

---

## 2. Methodology & Controls
Identical constraints to the V1 evaluation:
- **Retrieval Engine**: Qdrant Vector search
- **Embeddings**: `BAAI/bge-small-en-v1.5`
- **Generative Judge**: `llama-3.1-8b-instant` (Twin judges)
- **Top-K Search**: `k=5`
- **Portfolio Split**: 60% Enterprise Synthetic Data vs 40% Academic Research Data.

---

## 3. The Refactor: Targeted Code Fixes

| Strategy | Identified Flaw in V1 | Architectural Fix in V2 |
|---|---|---|
| **Fixed** | None. Was acting as the character-based control. | *No changes made.* |
| **Sliding Window** | Dynamically expanded chunk ends to sentences, but advanced the next chunk START using a blunt, rigid mathematical stride, tearing leading sentences in half. | **Sentence Alignment:** Intercepted both START and END boundaries using regex (`[.!?]\s+`), calculating overlap dynamically based on natural language instead of pure integers. |
| **Structure** | Oversized headings (>1500 chars) fell back to the Fixed chunker, but the "Heading" title was only attached to the first sub-chunk. Subsequent pieces lost context. | **Heading Stitching:** Intercepted the fallback system and prepended the exact `{Heading} (cont.)` string to all generated sub-chunks artificially binding the LLM's attention. |
| **Semantic** | Grouped topics perfectly, but lacked a maximum limit and had *zero* overlap bridging consecutive topics together, leading to high hallucinations. | **Bridging & Capping:** Added a hard `1500` char max-size rule, and forced the final sentence of Chunk A to be copied as the opening sentence of Chunk B spanning the contextual gap. |

---

## 4. Final Performance Impact (Before vs After)

The following table highlights the impact of the refactor. 

### Sliding Window (The New Benchmark) 🏆
The sentence-alignment fix stabilized the context window dramatically.
* **Faithfulness**: `2.94` ➔ **`3.34` (+13.6%)** 
* **Hallucination Rate**: `40.0%` ➔ **`28.0%` (-12pp)**
* **Efficiency Index**: `0.480` ➔ **`0.563` (+17.3%)**

### Structure (Domain Lifter) 📈
By ensuring the markdown headings carried over to all nested sub-chunks, the less-formal Enterprise synthetic data became much easier for Llama 3 to interpret.
* **Synthetic Faithfulness**: `2.93` ➔ **`3.33` (+13.6%)**
* **Hallucination Rate**: `40.0%` ➔ **`36.0%` (-4pp)**

### Semantic (The Hardest Problem) 🤔
The overlap bridge heavily reduced context loss, particularly lifting synthetic performance, though the dense ML grouping still falls slightly behind the simpler algorithms for open-domain tasks.
* **Synthetic Faithfulness**: `2.60` ➔ **`3.16` (+21.5%)**

### Fixed (Stable Baseline) ⚖️
Acted mostly within standard deviation variances as expected since the logic was untouched. 
* **Faithfulness**: `3.13` ➔ **`3.22` (+2.8%)**

---

## 5. Strategic Conclusions & Future Baseline

**1. Sliding Window is the New Default** 
By respecting natural sentence boundaries at both entry and exit points of the window, the **Sliding Window** strategy extracts maximum utility per token dollar (Efficiency Index: `0.563`), outproducing the simplistic Fixed method. This is our official ingestion approach going forward.

**2. Context Scaffolding is Non-Negotiable**
The Structure chunker proved that artificially injecting headers into middle-body text dramatically improves LLM understanding. If the text has no context (e.g. from a PDF middle-page), giving the LLM breadcrumbs drastically lowers hallucination.

**3. Next Phase: Retrieval Engine Layer**
With ingestion optimized, we have hit a ceiling on single-vector capability (`~66-76% Context Precision`). The next step in the DeepVault architecture is to introduce **Hybrid BM25 Keyword Search** merged with **Cross-Encoder Reranking**, evaluating strictly against this post-refactor Sliding Window baseline.
