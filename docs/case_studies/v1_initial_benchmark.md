# Case Study: DeepVault RAG Retrieval & Chunking Strategy Benchmarking

## 1. Executive Summary
This case study evaluates the DeepVault enterprise Retrieval-Augmented Generation (RAG) system running a comparative benchmark across four text chunking strategies: **Fixed**, **Sliding Window**, **Structure-based**, and **Semantic**. 

Using our newly deployed V2 Evaluation Engine, we tested approximately 200 question-answer sequences split between unstructured synthetic queries and formalized academic research queries. The evaluation measured system latency, retrieval precision, generation faithfulness, and token cost, ultimately boiling down to an "Efficiency Index" to map production viability.

**Key Finding:** Counter-intuitively, the **Fixed** chunking strategy slightly out-performed advanced context-aware methods (Semantic/Structure) in both Faithfulness and overall Efficiency, proving to be the most robust baseline for the current vector model configuration (`bge-small-en-v1.5`).

---

## 2. Methodology & Controls
The portfolio run executed with the following constraints:
- **Retrieval Engine**: Qdrant Vector search
- **Embeddings**: `BAAI/bge-small-en-v1.5`
- **Generative Judge**: `llama-3.1-8b-instant` (Twin judges for Relevance & Faithfulness)
- **Top-K Search**: `k=5`
- **Domain Distribution Constraints**: 60% Enterprise Synthetic Data vs 40% Academic Research Data.

---

## 3. Retrieval Performance: Precision & Recall

All four strategies exhibited incredibly consistent retrieval potency. 

| Strategy | Hit Rate (Recall @5) | Context Precision @1 |
| --- | --- | --- |
| **Fixed** | 93.3% | 75.5% |
| **Sliding** | 94.0% | 76.0% |
| **Structure** | 94.0% | 76.0% |
| **Semantic** | 94.0% | 76.0% |

> [!NOTE] 
> **Retrieval Parity Analysis**
> The `bge-small` embedding model handles varying chunk geometries exceptionally well. The 94% hit rate indicates that our document corpus is highly distinguishable in the vector space regardless of exactly how the paragraphs are split. Context Precision @1 (~76%) means 3 out of 4 queries retrieve the correct source document on the very first try, dominating the LLM's context window.

---

## 4. Generation Quality: Faithfulness & Hallucination

While retrieval was consistent, the actual **quality** of the generated answers (graded on a 1-5 scale) exposed variations.

| Strategy | Avg Faithfulness (1-5) | Hallucination Rate |
| --- | --- | --- |
| **Fixed** | **3.13** | **37.7%** |
| **Structure** | 3.08 | 40.0% |
| **Sliding** | 2.94 | 40.0% |
| **Semantic** | 2.86 | 44.0% |

> [!WARNING]
> **The Semantic Paradox**
> Although Semantic chunking is mathematically superior at keeping logical arguments together, it performed the worst in Faithfulness (2.86) and exhibited the highest hallucination rate (44%). This suggests that "neural topic shifting" may be creating chunks that are either too dense or lacking the necessary boundary boilerplate needed by Llama 3 to ground its responses. 

---

## 5. Domain Breakdown (Academic vs. Synthetic)

We segmented the results by question category to test domain resilience. 

- **Academic Research**: Highly structured prose, heavy vocabulary.
- **Enterprise Synthetic**: Unstructured, conversational, varied formats.

*(Score: Avg Faithfulness)*
- **Fixed:** Research `3.40` | Synthetic `3.00`
- **Structure:** Research `3.30` | Synthetic `2.93`
- **Semantic:** Research `3.25` | Synthetic `2.60`
- **Sliding:** Research `3.00` | Synthetic `2.90`

**Finding:** All strategies struggled more with Synthetic queries. However, **Structure** parsing held up better than Semantic parsing on the messy Synthetic data. If the corpus scales heavily into non-academic data, maintaining heading/structure boundaries is more reliable than semantic ML boundaries.

---

## 6. Cost-Benefit Analysis

Production viability comes down to cost. We modeled the token consumption natively utilizing Groq's USD per Million API pricing.

| Strategy | Cost / 1,000 Queries | Efficiency Index (Quality/$ spent) |
| --- | --- | --- |
| **Fixed** | 6.19¢ | **0.506** |
| **Structure** | 6.16¢ | 0.499 |
| **Sliding** | 6.11¢ | 0.480 |
| **Semantic** | **6.09¢** | 0.468 |

*Efficiency Index = Faithfulness Score / Cost*

> [!TIP]
> Semantic and Sliding chunking actually pull *fewer* tokens into the prompt due to slightly tighter average chunk boundaries, making them slightly cheaper (`~6.1¢` vs `~6.2¢` per 1000 queries). However, because Fixed provides a significantly higher quality yield, its **Efficiency Index** (value for money) rests firmly at the top.

---

## 7. Strategic Recommendations

Based on this 200-query benchmark run, we formally recommend the following architectural stances for DeepVault v2:

1. **Adopt "Structure" as the Production Default:** While "Fixed" technically edged out "Structure" in overall faithfulness (3.13 vs 3.08), Structure chunking guarantees context boundaries align with human headings (H1/H2/H3). As the corpus grows, naive Fixed blocks will inevitably shear critical sentences in half.
2. **Deprecate Semantic Chunking:** The token overhead required to calculate sentence-shift algorithms during ingestion is not justified by its bottom-tier performance in generative faithfulness (2.86) and severe hallucination rate on untidy synthetic data.
3. **Shift focus to Retrieval vs Chunking:** Given all chunkers cap out at ~76% Context Precision, future engineering cycles should pivot toward adding **Hybrid Search (BM25 + Vector)** and **Cross-Encoder Reranking** to solve the remaining 24% of missed first-hits, rather than micro-optimizing chunk boundaries.
