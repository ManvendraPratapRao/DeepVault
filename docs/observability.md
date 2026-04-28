# DeepVault Observability Guide

## Overview

DeepVault ships with a full production observability stack — Prometheus metrics scraping, three Grafana dashboards, structured JSON logging with correlation IDs, and detailed health check endpoints. All infrastructure is provisioned via Docker Compose and requires no manual configuration.

---

## Quick Start

```bash
# Start the full observability stack (Qdrant + Redis + Prometheus + Grafana + API)
docker compose -f docker/docker-compose.yml up -d

# Grafana UI
open http://localhost:3000   # admin / deepvault

# Prometheus UI (raw metrics)
open http://localhost:9090

# Prometheus scrape endpoint (on the API)
curl http://localhost:8000/metrics
```

---

## Prometheus Metrics

All metrics are prefixed with `deepvault_` and exposed at `GET /metrics` in Prometheus text format.

### HTTP Layer

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_http_requests_total` | Counter | `method`, `path`, `status_code` | Total HTTP requests |
| `deepvault_http_request_duration_seconds` | Histogram | `method`, `path` | End-to-end HTTP latency |

### RAG Query Pipeline

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_query_total` | Counter | `retrieval_strategy`, `chunking_strategy`, `status` | Total RAG queries |
| `deepvault_query_duration_seconds` | Histogram | `retrieval_strategy`, `chunking_strategy` | Full RAG pipeline latency |
| `deepvault_llm_tokens_total` | Counter | `token_type` (`prompt`/`completion`), `retrieval_strategy` | Token consumption |
| `deepvault_llm_cost_usd_total` | Counter | — | Cumulative LLM cost in USD |

### Caching

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_cache_operations_total` | Counter | `cache_type` (`query`/`embedding`), `result` (`hit`/`miss`) | Cache effectiveness |

### Ingestion

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `deepvault_ingestion_total` | Counter | `chunking_strategy`, `status` (`success`/`duplicate`/`error`) | Document ingestion events |

---

## Grafana Dashboards

Three pre-provisioned dashboards are available immediately after `docker compose up`.

### 1. System Overview (`deepvault-overview`)

**Purpose:** High-level operational health. First dashboard to check for production incidents.

**Panels:**
- Request rate (req/s) — by method, path, status code
- Query latency p50 / p95 — by retrieval strategy
- Query error rate — with red threshold at 30%
- Cache hit rate — gauge with green/yellow/red thresholds
- LLM token consumption (tokens/min) — by token type
- Total LLM cost (USD) — cumulative counter
- Query rate by strategy — full strategy × chunking matrix

### 2. LLM Cost & Token Analysis (`deepvault-llm-cost`)

**Purpose:** Cost visibility and burn rate monitoring. Use this to detect runaway token usage.

**Panels:**
- Total LLM cost (USD) — stat with colour thresholds
- Total tokens consumed — all-time counter
- Average cost per query — derived metric
- Average tokens per query — derived metric
- Token burn rate (tokens/min) — prompt vs completion split
- LLM cost rate (USD/hour) — rolling rate
- Token consumption by retrieval strategy — strategy breakdown

### 3. Retrieval Performance (`deepvault-retrieval`)

**Purpose:** Retrieval quality and latency analysis. Use this to compare strategies and detect regressions.

**Panels:**
- Query latency p50 / p95 — global stats with colour thresholds
- Cache hit rate — gauge
- Failed queries (1h) — error count with thresholds
- Latency p50/p95 by retrieval strategy — timeseries comparison
- Query rate by strategy — strategy × chunking matrix
- Cache hit vs miss rate — by cache type
- Ingestion rate by strategy — success/duplicate/error split

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
    "retrieval_strategy": "hybrid",
    "prompt_tokens": 892,
    "completion_tokens": 214
  }
}
```

**Correlation IDs:** Every HTTP request gets a `X-Request-ID` header injected by the request middleware. The same ID propagates through all log lines for that request, enabling end-to-end tracing via `jq '.extra_fields.request_id'`.

---

## Prometheus Scrape Configuration

The Prometheus config at `docker/prometheus/prometheus.yml` scrapes the API every 15 seconds:

```yaml
scrape_configs:
  - job_name: deepvault
    static_configs:
      - targets: ['deepvault-api:8000']
    scrape_interval: 15s
    metrics_path: /metrics
```

---

## Adding a New Metric

1. Define the metric as a singleton in `app/api/middleware/metrics.py`:
   ```python
   MY_COUNTER = Counter("deepvault_my_metric_total", "Description", ["label1"])
   ```

2. Call it from the appropriate service:
   ```python
   from app.api.middleware.metrics import MY_COUNTER
   MY_COUNTER.labels(label1="value").inc()
   ```

3. Add a panel to the relevant Grafana dashboard JSON in `docker/grafana/provisioning/dashboards/`.
