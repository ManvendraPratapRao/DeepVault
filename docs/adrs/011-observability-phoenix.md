# ADR-011: LLM Observability — Arize Phoenix Migration

**Status:** Accepted  
**Date:** 2026-06-16 (Updated 2026-07-03)  
**Author:** Manvendra Pratap Rao  

---

## Context

During the early phases, the system utilized a standard Prometheus + Grafana stack for observability. While this was adequate for HTTP metrics (request latency, error rates) and aggregate system-level monitoring, it fell short for LLM-specific observability. 

Specifically, standard metrics could not easily answer:
- *Why* did this specific query hallucinate?
- *What* was the exact prompt sent to Groq for `req_123abc`?
- *How much* did this specific multi-turn conversation cost?
- *How* are the sub-queries from the `QueryDecomposer` performing individually?

To build a production-grade RAG system, we need deep trace-level visibility into every step of the LLM pipeline, from query routing to retrieval to generation.

Candidates Evaluated: **Arize Phoenix**, **Langfuse**, **Prometheus (Status Quo)**, **Datadog LLM Observability**.

---

## Decision

**Migrate from Prometheus to Arize Phoenix via OpenTelemetry** for LLM telemetry, trace visibility, and evaluation tracking.

---

## Evaluation

### Arize Phoenix (Selected)

| Criterion | Assessment |
|-----------|------------|
| Trace Visibility | ✅ First-class OpenTelemetry support. Native visualizations for nested RAG traces (e.g., Query -> Router -> Retrieval -> LLM). |
| Feature Set | ✅ Powerful UI tailored specifically for RAG evaluations, embedding drift, and generation quality analysis. |
| Deployment | ✅ Runs purely locally as a standalone Docker container (`arize-phoenix`) alongside our stack without external SaaS dependencies. |
| Standardization | ✅ Relies on vendor-neutral OpenTelemetry (`opentelemetry-sdk`) instead of proprietary tracking decorators. |

### Langfuse

| Criterion | Assessment |
|-----------|------------|
| Trace Visibility | ✅ Excellent tracing using proprietary decorators. |
| Cost Tracking | ✅ Built-in token cost calculation. |
| Deployment | ⚠️ Requires spinning up a Langfuse web server *plus* a dedicated PostgreSQL database just for tracing, significantly bloating the `docker-compose` footprint compared to Phoenix. |

*Note: Langfuse was a very close second, but Arize Phoenix was chosen for its cleaner integration via standard OpenTelemetry, its zero-dependency local Docker image, and its superior focus on RAG evaluation datasets.*

### Prometheus + Grafana (Status Quo)

| Criterion | Assessment |
|-----------|------------|
| System Metrics | ✅ Excellent for CPU, RAM, and HTTP layer. |
| LLM Tracing | ❌ Extremely difficult. Prometheus is a time-series database, not a distributed tracing system. High cardinality labels (like `request_id` or `query_text`) cause performance degradation. |

**Rejected for LLM tracking:** We have stripped out the custom Prometheus middleware completely. All telemetry (including latency and token counts) will be handled by OTel spans sent to Phoenix.

---

## Consequences

**Positive:**
- Complete visibility into the `QueryRewriter` and `QueryService` logic per request via a visual waterfall diagram.
- Ability to view the exact retrieved chunks that were passed in the prompt for a given query.
- Phoenix acts as both a trace collector and an evaluation UI.
- Adherence to OpenTelemetry standards makes the system vendor-agnostic (we can swap Phoenix for Jaeger or Datadog by just changing the OTel exporter URL).

**Negative:**
- Requires replacing existing `metrics.py` calls with OpenTelemetry `tracer.start_as_current_span()` blocks.

---

## Implementation Strategy 

1. **Infrastructure:** Replace Prometheus and Grafana in `docker-compose.yml` with the `arizephoenix/phoenix` container.
2. **SDK:** Add `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, and `openinference-instrumentation` to dependencies.
3. **Instrumentation:**
   - Initialize the OTel provider in `app/infrastructure/tracing/setup.py`.
   - Wrap core services (`QueryService`, `IngestionService`) in manual OTel spans.
4. **Cleanup:** Delete `metrics.py`, uninstall `prometheus-client`, and remove `docker/grafana` resources.
