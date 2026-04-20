# ADR 002: Large Language Model (LLM) Provider Selection

## Status
Accepted

## Context
A functional Enterprise RAG pipeline fundamentally demands an inference engine capable of ingesting vast unstructured text snippets and formulating highly coherent, factually strict natural language responses. Constraints mapped globally meant we could not rely on proprietary OpenAI or Anthropic compute due to localized key access restrictions.

## Decision
We elected to exclusively integrate **GroqCloud Network** serving **Meta Llama-3.1-8b-instant** as the primary Language Model throughout Phase 1 implementation.

## Rationale
1. **LPU Accelerator Advantage**: Groq executes instructions utilizing dedicated Language Processing Units (LPUs) achieving categorically unmatched speed architectures (+800 tokens/sec). Fast response curves are essential to perceived UX when combining Vector Retrieval networking latency overheads.
2. **Access Symmetry**: The current free-tier constraints of Groq inherently provide more than adequate compute allocations for building and natively testing a local prototype without immediate Enterprise rate-limiting restrictions shutting down testing matrixes.
3. **Open-Source Compatibility**: Utilizing the Llama-3.1 architectures dynamically guarantees standard generic Instruct/Chat boundaries, enabling completely unhindered migrations toward self-hosted variants mathematically identical (e.g. vLLM servers) in the future.

## Consequences
- **Positive**: We achieve hyper-fast RAG generations natively via standardized interfaces.
- **Negative (Mitigated)**: Groq restricts concurrent connection scaling aggressively on basic access tiers. We compensated extensively for this directly by developing the `RedisCache` injection layer which functionally prevents duplicate API calls and caches generations up to 1 Hour.
- **Future Implication**: During later Project Phases (Phase 5/6), the architecture will logically mature to support an intelligent router utilizing larger 70b-parameter variants for complex queries, parsing mathematically between 8b and 70b clusters.
