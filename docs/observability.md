# DeepVault Observability Guide

## Overview

DeepVault ships with a modern, full-stack observability solution powered by **OpenTelemetry (OTel)** and **Arize Phoenix**. 

All tracing, LLM span logging, and pipeline monitoring is implemented natively through the OpenTelemetry SDK. The infrastructure is provisioned via Docker Compose and requires zero manual configuration.

---

## Quick Start

```bash
# Start the full observability stack (Qdrant + Redis + Phoenix + API)
docker compose -f docker/docker-compose.yml up -d

# Arize Phoenix UI
open http://localhost:6006

# API Health
curl http://localhost:8000/api/v1/health/detailed
```

---

## Arize Phoenix (OTel Backend)

We use Arize Phoenix as our unified LLM observability platform. It acts as the OTel collector and provides a dedicated UI for LLM traces.

### What is Traced?
1. **HTTP Requests:** Every incoming API call.
2. **Retrieval Pipelines:** Complete traces of `QdrantVectorStore` queries and caching operations.
3. **Query Rewriting:** Before/After states of the `QueryRewriter`.
4. **LLM Generation:** Exact prompt sent to Groq and the completion received.
5. **Ingestion Pipelines:** Chunking strategy boundaries, metadata extraction, and vector embedding latency.

### Phoenix UI (`http://localhost:6006`)
- **Traces:** View the exact waterfall diagram of a query.
- **Spans:** Drill down into LLM specific operations (tokens used, latency, exact payload).
- **Datasets:** (For evaluation framework integration).

---

## OpenTelemetry Implementation

Tracing is initialized in `app/infrastructure/tracing/setup.py`.

### Injecting Custom Spans
You can trace custom business logic by wrapping it in an OTel tracer span:

```python
from opentelemetry import trace

tracer = trace.get_tracer("deepvault.services")

with tracer.start_as_current_span("MyCustomOperation") as span:
    span.set_attribute("custom.field", "value")
    # ... your code here
```

---

## Health Check Endpoints

### Basic Liveness
```bash
GET /api/v1/health
```

Returns `200 OK` if the API is running. Returns `degraded` status if any dependency is down.

```json
{
  "status": "healthy",
  "version": "3.0.0",
  "timestamp": "2026-04-28T12:00:00Z"
}
```

### Detailed Component Health
```bash
GET /api/v1/health/detailed
```

Probes each dependency with per-component latency:
```json
{
  "status": "healthy",
  "components": {
    "redis": { "status": "healthy", "latency_ms": 0.8 },
    "qdrant": { "status": "healthy", "latency_ms": 2.1 },
    "llm": { "status": "healthy", "latency_ms": 412.0 }
  }
}
```

---

## Structured Logging

Every log line is output as JSON with the following fields:

```json
{
  "timestamp": "2026-04-28T12:00:00.123Z",
  "level": "INFO",
  "message": "Query answered successfully (Cache Miss)",
  "module": "query",
  "function": "ask",
  "extra_fields": {
    "request_id": "abc-123",
    "latency_ms": 1247.3,
    "num_sources": 5,
    "retrieval_strategy": "hybrid_rerank"
  }
}
```

**Correlation IDs:** Every HTTP request gets an `X-Request-ID` header injected by the middleware. The same ID propagates through all log lines for that request.
