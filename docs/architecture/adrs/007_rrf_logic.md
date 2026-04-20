# ADR-007: RRF vs. Weighted Score Merging

*   **Status**: Accepted
*   **Date**: 2026-04-14
*   **Decider**: Antigravity (AI Architect)

## Context and Problem Statement

For Hybrid Retrieval, we must combine results from two fundamentally different scoring systems:
1.  **Vector Search**: Dot Product or Cosine Similarity (floating point scores).
2.  **BM25 Search**: Term-frequency based scores (logarithmic scales).

We need a method to merge these results into a single ranking without the bias of incompatible score magnitudes.

## Decision Drivers

1.  **Robustness**: The merging logic should not break if one retriever changes its scoring range (e.g., swapping a Dot-Product embedder for a Cosine-Similarity one).
2.  **Simplicity**: Avoid complex hyperparameter tuning where possible.
3.  **Accuracy**: Prioritize documents that appear high in *both* lists.

## Considered Options

1.  **Weighted Linear Combination**: `FinalScore = (alpha * VectorScore) + (beta * BM25Score)`.
2.  **Reciprocal Rank Fusion (RRF)**: Merging based on rank position rather than raw score.
3.  **Hybrid Reranking (Only)**: Use one as a filter and the other as a scorer.

## Decision Outcome

Chosen Option: **Reciprocal Rank Fusion (RRF)**

### Reasons
-   **Score Agnosticism**: RRF doesn't care about the raw scores; it only cares about the **rank index**. This makes it incredibly stable across different embedding models.
-   **Collaborative Filtering**: Documents that are ranked highly by both retrievers receive a significant boost, ensuring the LLM gets context that is both semantically relevant and keyword-accurate.
-   **No Normalization Req**: No need to spend compute cycles normalizing BM25 scores (which can range from 0 to 100+) to fit Vector scores (usually 0 to 1).

## Consequences

-   **Hyperparameters**: We use a default `k=60` to balance the impact of top-ranked items.
-   **Performance**: RRF is highly efficient, requiring only a dictionary-based merge during the retrieval pass.
