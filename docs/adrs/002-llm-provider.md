# ADR-002: LLM Provider — Groq (Llama-3.1)

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Manvendra Pratap Rao

---

## Context

DeepVault requires an LLM for two distinct tasks:

1. **Answer generation** — Given retrieved context and a user question, generate a grounded, factual response.
2. **LLM-as-judge evaluation** — Score retrieved answers on faithfulness (1–5) and relevance (1–5) for the automated benchmark pipeline.

The LLM provider must satisfy:
- Low latency (target: <2 seconds for answer generation at p50).
- Low cost (the evaluation pipeline runs 700+ queries per benchmark pass; cost must be manageable).
- No data retention or privacy concerns during development.
- A clean Python client that works with `asyncio`.
- Support for both small (fast/cheap) and large (accurate judge) models in the same API.

Candidates evaluated: **Groq**, **OpenAI**, **Anthropic**, **Ollama (local)**.

---

## Decision

**Use Groq** as the sole LLM provider.

**Phase 4 Update (LLM Routing):** With the introduction of the `LLMRouter`, we dynamically select the model based on the query class:
- `llama-3.1-8b-instant`: Used for `factual` queries where speed is paramount and reasoning overhead is low.
- `llama-3.3-70b-versatile`: Used for `semantic`, `comparison`, and `complex` queries that require advanced reasoning. It is also used as the LLM-as-a-judge for evaluation.

---

## Evaluation

### Groq

| Criterion | Assessment |
|-----------|------------|
| Inference speed | ✅ Groq's LPU (Language Processing Unit) delivers 300–800 tok/s vs ~50-80 tok/s on OpenAI. |
| Free tier | ✅ Generous rate limits on the free plan; sufficient for full benchmark runs. |
| Cost | ✅ `llama-3.1-8b-instant` is effectively free at development scale. |
| Model quality | ✅ Llama-3.1 8B is competitive for RAG answer synthesis. 70B is excellent for judging. |
| Vendor lock-in | ✅ Llama models are open weights — could self-host if Groq changes pricing. |
| OpenAI-compatible API | ✅ Uses the same `openai` client library. Migration to other providers is trivial. |
| Streaming support | ✅ Full SSE streaming supported (`client.chat.completions.create(..., stream=True)`). |

### OpenAI (GPT-4o / GPT-3.5-turbo)

| Criterion | Assessment |
|-----------|------------|
| Inference speed | ⚠️ GPT-4o averages ~30-50 tok/s. 10× slower than Groq for long contexts. |
| Cost | ⚠️ GPT-3.5-turbo is cheap; GPT-4o is expensive. A 700-query eval run on GPT-4o would cost ~$15-40. |
| Model quality | ✅ Best-in-class quality. |
| Data retention | ⚠️ API data may be used for training unless opted out (Enterprise plan required). |

**Rejected:** Cost at evaluation scale is prohibitive. Groq's LPU speed is a better fit for a high-throughput eval pipeline.

### Anthropic (Claude 3.5 Sonnet)

| Criterion | Assessment |
|-----------|------------|
| Inference speed | ⚠️ Comparable to OpenAI. Not LPU-optimized. |
| Cost | ⚠️ More expensive than Groq for equivalent quality at scale. |
| API | ✅ Good async client. |

**Rejected:** Same cost concerns as OpenAI. No compelling advantage for this use case.

### Ollama (Local Models)

| Criterion | Assessment |
|-----------|------------|
| Cost | ✅ Free. |
| Privacy | ✅ Fully local. |
| Speed | ❌ CPU-bound on developer hardware. 8B model on CPU: ~5-15 tok/s. Eval runs would take hours. |
| Deployment | ❌ Requires local GPU for acceptable performance. Not portable. |

**Rejected:** Local inference speed on CPU is too slow for the evaluation pipeline's 700+ calls per benchmark run.

---

## Consequences

**Positive:**
- Sub-second LLM latency enables real-time query responses without streaming.
- Groq's free tier makes full benchmark runs (700+ LLM calls) cost-free during development.
- The `openai`-compatible client means zero migration cost to switch providers.
- Using separate 8B (generation) and 70B (judging) models gives the best quality-cost tradeoff.

**Negative:**
- Groq rate limits may require retry logic and backoff during large eval runs.
- Groq is a third-party dependency — if they change pricing or shut down, the LLM must be swapped.
- The 8B model has a lower quality ceiling than GPT-4o for complex multi-hop reasoning.

---

## Implementation Notes

- `GroqLLMClient` in `app/infrastructure/llm/groq.py` wraps the `groq` SDK with async support.
- The client returns an `LLMResult` dataclass containing `answer`, `usage` (token counts), and `model`.
- Token usage is tracked per query and aggregated in the evaluation engine for cost reporting.
- Retry logic: the eval engine implements exponential backoff with up to 3 retries on rate limit errors (HTTP 429).
- Model configuration: set `GROQ_MODEL_NAME` in `.env`. Default: `llama-3.1-8b-instant`.
