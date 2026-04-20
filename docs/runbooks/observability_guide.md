# Observability Guide — Prometheus Metrics and Grafana

**Phase:** 4 (Production Hardening)  
**Status:** Planned — Implementation Pending (Session 17–18)

---

## Overview

This document describes the planned observability stack for DeepVault. The goal is to expose production metrics via a `/metrics` endpoint (Prometheus) and visualize them through Grafana dashboards.

---

## Planned Metrics

### Query Latency

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_query_duration_seconds` | Histogram | `chunking_strategy`, `retrieval_strategy` | End-to-end query latency |
| `deepvault_retrieval_duration_seconds` | Histogram | `retrieval_strategy` | Retrieval-only latency |
| `deepvault_llm_duration_seconds` | Histogram | `model` | LLM generation latency |
| `deepvault_reranking_duration_seconds` | Histogram | — | Cross-encoder reranking latency |

### Throughput and Errors

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_queries_total` | Counter | `status` (success/error), `retrieval_strategy` | Total queries processed |
| `deepvault_ingestion_documents_total` | Counter | `chunking_strategy` | Documents ingested |
| `deepvault_errors_total` | Counter | `error_type` | Total errors by type |

### Cache Performance

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_cache_hits_total` | Counter | `cache_type` (query/embedding) | Cache hits |
| `deepvault_cache_misses_total` | Counter | `cache_type` | Cache misses |

### LLM Cost Tracking

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_llm_tokens_total` | Counter | `model`, `token_type` (prompt/completion) | Token consumption |
| `deepvault_llm_cost_usd_total` | Counter | `model` | Estimated USD cost |

---

## Implementation Plan (Session 17)

### 1. Add prometheus-client dependency

```toml
# pyproject.toml
[tool.uv.dependencies]
prometheus-client = ">=0.20"
```

### 2. Create Metrics Middleware

```python
# app/api/middleware/metrics.py
from prometheus_client import Counter, Histogram, make_asgi_app
import time

QUERY_DURATION = Histogram(
    "deepvault_query_duration_seconds",
    "End-to-end query latency",
    labelnames=["retrieval_strategy", "chunking_strategy"]
)

QUERY_TOTAL = Counter(
    "deepvault_queries_total",
    "Total queries processed",
    labelnames=["status", "retrieval_strategy"]
)
```

### 3. Expose /metrics Endpoint

```python
# app/main.py
from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

---

## Grafana Dashboard Configuration (Session 18)

Three dashboards are planned:

### Dashboard 1: System Overview
- Query rate (req/min)
- p50/p95/p99 query latency
- Error rate
- Cache hit rate

### Dashboard 2: LLM Cost Tracker
- Tokens per hour (prompt vs completion)
- Estimated cost per hour (USD)
- Cost by retrieval strategy
- Running total cost

### Dashboard 3: Retrieval Performance
- Hit rate by chunking strategy
- Latency by retrieval strategy (vector vs hybrid vs hybrid_rerank)
- Reranking latency overhead

---

## Docker Compose Setup (Session 18)

Add Prometheus and Grafana to `docker/docker-compose.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:v2.50.0
    ports:
      - "9090:9090"
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    volumes:
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=deepvault
```

Prometheus scrape config (`docker/prometheus.yml`):

```yaml
scrape_configs:
  - job_name: "deepvault"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: "/metrics"
    scrape_interval: 15s
```

---

## Current Observability (Available Now)

While Prometheus is pending, DeepVault already provides:

- **Structured JSON logs** — every request has a correlation ID, latency, token usage, and cache status.
- **Token usage** in `QueryResponse.usage` — prompt tokens, completion tokens, model name.
- **Eval pipeline cost tracking** — per-query cost in `data/eval_runs/*/token_usage.json`.
- **Health endpoint** — `GET /api/v1/health` checks Qdrant, Redis, and embedder status.

To view live logs during development:

```bash
# JSON logs from the running API
make dev 2>&1 | python -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"
```
