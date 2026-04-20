# DeepVault Architecture: Hybrid Retrieval & Reranking

This document explains the technical rationale and implementation details of the new DeepVault Retrieval Engine.

## Why Hybrid? (The Keyword + Context Problem)

Individual retrieval strategies have specific blind spots:
1.  **Vector Search (Semantic)**: Uses embeddings to find meaning. 
    - *Strength*: Understands intent (e.g., "how do I fix a bug" finds "debugging guide").
    - *Weakness*: Struggles with exact identifiers, unique names, or rare keywords (e.g., searching for "Error ID: X-200" might return a general "Common Errors" guide instead of the specific entry for X-200).
2.  **BM25 (Keyword)**: Statistical keyword matching.
    - *Strength*: Perfect for exact matches and "finding a needle in a haystack" by unique terms.
    - *Weakness*: No understanding of synonyms or context.

**Hybrid Retrieval** merges these two worlds into one "Unified List".

## How it Works: Reciprocal Rank Fusion (RRF)

When we have two different lists (one from Vector, one from BM25) with different scoring scales, we cannot simply add their scores together. Instead, we use **RRF**.

### The RRF Formula:
$$Score(d) = \sum_{r \in R} \frac{权重}{k + Rank(d, r)}$$

-   **$Rank(d, r)$**: The position of document $d$ in result list $r$.
-   **$k$**: A constant (usually 60) that prevents high-ranking items from totally dominating the fused list.
-   **Weighted**: We give users control over how much to trust Vector vs. Keyword matches.

## Why Hybrid + Reranker? (The Precision problem)

Retrieval (Vector/Keyword) is designed to filter millions of documents down to 20 or 50. It is fast but relative. 

**The Cross-Encoder Reranker** is our "Master Judge". Unlike retrieval models that look at Query and Document separately, a Cross-Encoder looks at them **simultaneously** using self-attention.

### The Pipeline:
1.  **Retrieve (Wide Net)**: Fetch the top 20 candidate chunks using Hybrid RRF.
2.  **Rerank (Contextual Scrutiny)**: Send those 20 candidates to the Cross-Encoder.
3.  **Synthesize (Filtered Context)**: Pass only the top 5 "reranked" chunks to the LLM.

This "Fetch 20 -> Prune to 5" strategy creates a massive jump in precision by ensuring the LLM sees only the most contextually relevant signals.

## File System & Project Design

-   **`app/core/interfaces/`**: We use Abstract Base Classes (ABCs) like `BaseRetriever` and `BaseReranker`. This allows us to swap a "MiniLM" reranker for a "BGE-Reranker" or a "Cohere API" without changing any service code.
-   **`app/infrastructure/`**: Contains the heavy lifting (Qdrant, Redis, Rank-BM25).
-   **`data/eval_runs/`**: Organized by retrieval strategy to prevent benchmark "contamination" and allow for side-by-side performance comparisons.

## Evaluation Process

Our Evaluation Engine (`scripts/eval_engine_metrics.py`) simulates a human judge:
1.  **Asks**: Passes 30 unique questions to the system.
2.  **Generates**: Gets an answer using the current strategy.
3.  **Judges**: Uses a separate LLM (Llama-3.1-8b) to grade the answer on **Faithfulness** (no hallucinations) and **Relevance**.
4.  **Telemetrizes**: Calculates P50, P95, and P99 latencies and cost-per-query.
