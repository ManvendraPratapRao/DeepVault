# DeepVault Observability & Debugging Guide

DeepVault has been upgraded from "Silent Failure" mode to "Hardened High-Fidelity" mode. This guide explains how to use the new observability tools to debug and stabilize the RAG pipeline.

## 🔴 The "Red Alert" Exception Handler
We have implemented a global "Red Alert" handler in [main.py](file:///d:/ML%20PROJECTS/deepvault/app/main.py). 

### How it Works:
If any unhandled exception occurs in the FastAPI backbone, the system will:
1.  **Intercept** the crash before it returns a generic 500.
2.  **Extract** the full Python traceback.
3.  **Explode** the output into your terminal/stderr with high-fidelity formatting.
4.  **Assigne** a unique `request_id` to correlate the error across the API and the UI.

### Interpretation:
When you see a large block of text starting with `🔥 DEEPVAULT CRITICAL ERROR`, look for:
- **Error Type**: (e.g., `AuthenticationError`, `ValidationError`)
- **Traceback**: The exact line in the code where the failure originated.
- **Request ID**: Use this to find relevant logs in the JSON stream.

---

## 📊 Structured JSON Logging
All application logs are now output as structured JSON. This is essential for professional monitoring and automated analysis.

### Standard Log Format:
```json
{
  "timestamp": "2026-04-10T04:19:26.319503+00:00",
  "level": "INFO",
  "message": "Query answered successfully (Cache Miss)",
  "module": "query",
  "function": "ask",
  "request_id": "50438a1c-b712-49c1-b8f3-0b6c632f3fe4",
  "latency_ms": 989.6,
  "cache_miss": true
}
```

### Pro-Tips for Debugging:
- **Filtering**: Use `grep` or a local log viewer to filter by `request_id`.
- **Latency Tracking**: Every response log includes `latency_ms`. Use this to find bottlenecks in the Embedding vs. Retrieval vs. Generation phases.

---

## 🧪 Health Check Protocols
Before declaring a production crisis, run these two built-in diagnostics:

1. **Authentication Check**:
   ```pwsh
   uv run python scratch/auth_diagnostic.py
   ```
   *Validates if your `.env` key is being shadowed or if it contains non-ASCII characters.*

2. **Victory Check**:
   ```pwsh
   uv run python scratch/final_victory_check.py
   ```
   *Tests the complete end-to-end RAG loop (Qdrant -> Groq).*

---

## 🚀 Best Practices for Maintenance
- **Key Changes**: When updating API keys, always restart the terminal session and run `.\dev.ps1` to clear environment caches.
- **SDK Updates**: If you update `qdrant-client`, always check [qdrant.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/stores/qdrant.py) for dialect shifts in `.query_points()`.
