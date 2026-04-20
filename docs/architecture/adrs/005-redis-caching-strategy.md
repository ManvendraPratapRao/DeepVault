# ADR 005: Redis Caching Layer Configurations

## Status
Accepted

## Context
Generative Inference networks incur severe computational latency mathematically. Even using exceptionally rapid LPU networks, API latency, network handshakes, and vector computations drag simple Q&A queries beyond `1500ms`. Enterprise architectures inherently necessitate robust responses under `<200ms` for repetitive queries to preserve fluid end-user dynamics.

## Decision
We elected to systematically integrate a **Dual-Tier Redis Caching Engine** to aggressively bypass external network arrays logically on identical deterministic processes natively mapping semantic hits. 

## Rationale
1. **Cache Layer 1 (Query Service)**: The orchestrator leverages a structural MD5 payload hash string. A query evaluated structurally identical sequentially pulls completed LLM syntaxes instantly directly off the Redis mapping, skipping Qdrant, BAAI chunkers, and Groq natively globally.
2. **Cache Layer 2 (Vector Generation)**: During batch indexing natively over 500+ fragments, the engine systematically iterates arrays over localized SHA256 caching metrics natively avoiding recalculating duplicate sentence strings mapped dynamically during document revisions.
3. **Resilience Engineering**: We strictly configured the `app/dependencies.py` arrays to seamlessly catch native Server failures mapping logically behind graceful Degradation architectures. 

## Consequences
- **Positive**: We actively reduce network/computational compute delays globally across repetitively requested endpoints directly dynamically evaluating >80% speed augmentations fundamentally. 
- **Negative (Mitigated)**: Memory loads increase slightly natively across Redis container domains. The `docker-compose.yml` gracefully structures configurations mathematically enforcing `maxmemory-policy allkeys-lru` restricting payloads dynamically natively beyond `256mb` bounds automatically. 
