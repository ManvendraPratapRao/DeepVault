# DeepVault Deployment Guide

**Phase:** 4 (Production Hardening)  
**Status:** Scaffold — Implementation Pending

---

## Overview

This guide covers deploying DeepVault from a local development environment to a production-ready system. It covers Docker-based local deployment, environment configuration, and a step-by-step AWS EC2 free-tier deployment.

---

## Prerequisites

| Dependency | Version | Notes |
|-----------|---------|-------|
| Python | 3.12+ | Required. Use `uv` for environment management. |
| Docker | 24+ | For Redis, Qdrant, and the API container. |
| Docker Compose | v2 | Bundled with Docker Desktop. |
| Groq API Key | — | Free at [console.groq.com](https://console.groq.com). |
| `uv` | latest | `pip install uv` |

---

## Local Development Deployment

### 1. Clone and Install

```bash
git clone https://github.com/ManvendraPratapRao/DeepVault.git
cd DeepVault
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```env
GROQ_API_KEY=gsk_your_key_here
API_KEY=deepvault_secret_key

# Infrastructure
QDRANT_HOST=localhost
QDRANT_PORT=6333
REDIS_HOST=localhost
REDIS_PORT=6379

# App settings
CHUNKER_STRATEGY=fixed
RETRIEVAL_STRATEGY=hybrid
LOG_LEVEL=INFO
CACHE_ENABLED=true
EMBEDDING_CACHE_ENABLED=true
```

### 3. Start Infrastructure

```bash
make docker-up
# Starts: Redis 7 (port 6379) + Qdrant (ports 6333, 6334)
```

### 4. Seed the Knowledge Base

```bash
# All 4 chunking strategy collections
make seed-all

# Single strategy
make seed CHUNKER=fixed
```

### 5. Start the API

```bash
make dev
# API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

### 6. Launch the Dashboard (Optional)

```bash
make ui
# Streamlit: http://localhost:8501
```

---

## Docker Compose Full Stack

The `docker/docker-compose.yml` file runs the full stack (API + Redis + Qdrant):

```bash
docker compose -f docker/docker-compose.yml up --build
```

Services:
- **api** — DeepVault FastAPI (port 8000)
- **redis** — Redis 7 (port 6379)
- **qdrant** — Qdrant vector DB (port 6333)

Healthchecks are configured for all three services.

For the API service, set `GROQ_API_KEY` as an environment variable or in a `.env` file at the project root.

---

## AWS EC2 Free-Tier Deployment

> **Instance type:** `t2.micro` or `t3.micro` (1 vCPU, 1GB RAM). Groq's Llama inference is remote, so no GPU needed.

### Step 1: Launch EC2 Instance

1. Go to AWS Console → EC2 → Launch Instance.
2. Select **Ubuntu Server 22.04 LTS**.
3. Instance type: `t3.micro` (free tier eligible).
4. Create/select a key pair (`.pem` file for SSH).
5. Security Group — add inbound rules:
   - SSH (port 22) — your IP only.
   - HTTP (port 8000) — `0.0.0.0/0` (API).
   - HTTP (port 8501) — `0.0.0.0/0` (Streamlit, optional).
6. Launch instance.

### Step 2: Install Dependencies

```bash
# SSH into the instance
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### Step 3: Clone and Configure

```bash
git clone https://github.com/ManvendraPratapRao/DeepVault.git
cd DeepVault

# Create .env file
cat > .env << EOF
GROQ_API_KEY=gsk_your_key_here
QDRANT_HOST=localhost
REDIS_HOST=localhost
CACHE_ENABLED=true
RETRIEVAL_STRATEGY=hybrid
EOF
```

### Step 4: Start the Stack

```bash
sudo docker compose -f docker/docker-compose.yml up -d --build
```

### Step 5: Seed Data

```bash
# Wait for services to be ready
sleep 10

# Seed with the recommended strategy
sudo uv run python scripts/seed.py --strategy fixed
```

### Step 6: Verify

```bash
curl http://<EC2_PUBLIC_IP>:8000/api/v1/health
# Expected: {"status": "healthy", ...}
```

---

## Environment Variables Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | — | ✅ | Groq API key for LLM inference |
| `API_KEY` | `deepvault_secret_key` | ✅ | Bearer token for API authentication |
| `QDRANT_HOST` | `localhost` | — | Qdrant server hostname |
| `QDRANT_PORT` | `6333` | — | Qdrant REST port |
| `REDIS_HOST` | `localhost` | — | Redis hostname |
| `REDIS_PORT` | `6379` | — | Redis port |
| `CHUNKER_STRATEGY` | `fixed` | — | Default chunking strategy |
| `RETRIEVAL_STRATEGY` | `vector` | — | Default retrieval strategy |
| `LOG_LEVEL` | `INFO` | — | Logging level (`DEBUG`/`INFO`/`WARNING`) |
| `CACHE_ENABLED` | `true` | — | Enable/disable query cache |
| `EMBEDDING_CACHE_ENABLED` | `true` | — | Enable/disable embedding cache |
| `GROQ_MODEL_NAME` | `llama-3.1-8b-instant` | — | LLM model for generation |

---

## Production Checklist

Before exposing to production traffic:

- [ ] Change `API_KEY` from the default value
- [ ] Set `DEBUG=false`
- [ ] Configure a reverse proxy (Nginx/Caddy) in front of port 8000
- [ ] Enable HTTPS (Let's Encrypt with Certbot)
- [ ] Set `LOG_LEVEL=WARNING` for production
- [ ] Configure Redis with `requirepass` for password auth
- [ ] Set up automated backups for `deepvault.db` (SQLite)
- [ ] Set up automated backups for `qdrant_storage/` directory

---

## Phase 4 Planned Additions

The following production hardening features are planned for Phase 4:

- **Prometheus metrics** (`/metrics` endpoint) — see `docs/runbooks/observability_guide.md`
- **Grafana dashboards** — latency, LLM cost, cache hit rate
- **JWT authentication** — replace static `API_KEY` with role-based tokens — see `docs/runbooks/auth_guide.md`
- **PostgreSQL migration** — replace SQLite for multi-worker deployments
- **SSE streaming** — streaming response endpoint for chat-like UX
