# The DeepVault Query Pipeline

This document walks through the exact lifecycle of a user query in DeepVault. Our system goes far beyond a naive "embed query -> search -> pass to LLM" RAG flow. We use an intelligent, multi-stage pipeline designed for high precision and robustness against complex edge cases.

## The Pipeline Lifecycle

When a request arrives at `POST /api/v1/query` or `POST /api/v1/stream`, it flows through the following stages:

### Stage 1: The Semantic Cache Layer (Redis)

Before doing any expensive work, the `QueryService` checks the Redis cache.
- We perform a fast string match (or semantic match if enabled).
- If a match is found, the response is returned instantly (typically <2ms).
- Cache misses proceed to Stage 2.

### Stage 2: Query Intelligence (The Router & Decomposer)

Instead of statically wiring a single retrieval strategy, DeepVault analyzes the query in real-time.

1. **Classification:** The `QueryClassifier` runs a regex/heuristic ruleset to determine the query's intent (`factual`, `semantic`, `comparison`, or `complex`).
2. **Strategy Routing:** Based on the class, the `QueryRouter` picks the best underlying retrieval mechanism.
    - Factual -> Hybrid Search (BM25 helps catch exact names/acronyms).
    - Semantic -> Vector Search.
    - Comparison -> Hybrid + Reranker.
3. **Decomposition:** If the query is flagged as `complex` (e.g., "What is X and how does it compare to Y?"), the `QueryDecomposer` kicks in. It uses an LLM to break the query into 2-4 focused sub-queries.

### Stage 3: Retrieval & Merging

With the strategy decided (and sub-queries generated if applicable), we hit Qdrant.
- **For standard queries:** We run the selected strategy (Vector, BM25, or Hybrid).
- **For complex queries:** We run the selected strategy *for each sub-query* in parallel using `asyncio.gather`. The results are then merged and deduplicated.
- **Hybrid Fusion:** If a Hybrid strategy is used, results from Vector and BM25 are fused using Reciprocal Rank Fusion (RRF).

### Stage 4: Reranking (Optional)

If the `hybrid_rerank` strategy was selected, we take the top `K*4` candidates from Stage 3 and pass them through a Cross-Encoder model. The Cross-Encoder computes a highly accurate semantic match score between the query and each chunk, outputting the final top `K`.

### Stage 5: The Context Confidence Guard

This is a critical safety mechanism. We check the relevance score of the top retrieved chunk.
- If the score is below `settings.CONTEXT_CONFIDENCE_THRESHOLD`, we intercept the pipeline.
- Instead of passing irrelevant context to the LLM and risking a "confident hallucination", we immediately return a standard refusal: *"I don't have sufficient information in the knowledge base..."*

### Stage 6: LLM Routing and Generation

If the context passes the guard, we build the final prompt.
- **LLM Router:** The `LLMRouter` decides which model to use. Factual queries are routed to the fast/cheap model (`llama-3.1-8b-instant`), while complex/semantic queries get the heavy lifter (`llama-3.3-70b-versatile`).
- **Generation:** The context and query are injected into the `RAG_USER_TEMPLATE`, combined with the `RAG_SYSTEM_PROMPT` to enforce groundedness, and sent to Groq.
- **Streaming:** If using the `/stream` endpoint, tokens are yielded via SSE as soon as Groq produces them.

### Stage 7: Telemetry and Caching

After the answer is generated (or while the stream completes in a background task):
- **Metrics:** Request duration, token usage, and hit rates are sent to Prometheus.
- **Caching:** The final query-answer pair is saved to Redis to benefit future users.
