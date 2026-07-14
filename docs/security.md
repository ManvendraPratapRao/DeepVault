# Security & Threat Model

DeepVault is designed to handle enterprise data. This document outlines our current security posture, threat model, and areas slated for future hardening.

## Current Security Controls

### 1. API Authentication
- The API is secured via a static Bearer Token (`X-API-KEY`).
- Unauthorized requests receive a `403 Forbidden` response.

### 2. Rate Limiting
- A sliding-window rate limiter (backed by Redis) protects the API from abuse and denial-of-wallet attacks against the Groq LLM API.
- Rate limits are enforced on a per-API-key basis.

### 3. Context Confidence Guard
- **Threat:** Hallucination / Misinformation.
- **Control:** The RAG pipeline checks the vector similarity score of retrieved chunks. If the confidence is below the configured threshold, the LLM is preempted, and a safe "I don't know" response is returned.

### 4. Injection Protection
- **Prompt Injection:** RAG user prompts are strongly sandboxed using strict templates. The retrieved context and the user's question are interpolated safely.
- **SQL Injection:** We use `aiosqlite` with parameterized queries for all metadata operations. No raw SQL concatenation is used.

## Known Gaps (Roadmap)

The following items are planned for future phases:

1. **Multi-Tenant / JWT Auth (Phase 5):** The single static API key is insufficient for multi-user production. We plan to migrate to OAuth2/JWT with role-based access control (RBAC), allowing document-level permissions (e.g., User A can query HR docs, User B cannot).
2. **Data Encryption at Rest:** Currently, Qdrant and SQLite store data in plaintext on disk. Production deployments should utilize encrypted EBS volumes.
3. **PII Redaction:** Implement a middleware layer (e.g., using Microsoft Presidio) to redact Personally Identifiable Information from user queries before they are sent to the external Groq LLM.
4. **Langfuse Integration:** Transitioning to Langfuse (v2 Lite) will improve our audit logging, allowing us to track exactly which user made which query and what the LLM generated.
