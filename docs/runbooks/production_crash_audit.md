# DeepVault Production Crash Audit: The Stabilization Journey

This document serves as a holistic post-mortem of the technical crisis encountered during the transition of DeepVault from a prototype to a hardened production RAG system.

## 🔴 The Crisis Overview
The project was in a state of "Silent Failure," where API requests would return a generic `500 Internal Server Error` without actionable tracebacks. The pipeline suffered from three distinct but overlapping failure vectors:
1. **SDK Dialect Incompatibility** (The AttributeError)
2. **Schema Polarization** (The Serialization Friction)
3. **Environment Hijacking** (The Ghost Key)

---

## 🕵️ Failure Vector 1: The Vector Store "Amnesia"
### The Problem
Core retrieval was completely paralyzed. The `QdrantVectorStore` was throwing an `AttributeError: 'AsyncQdrantClient' object has no attribute 'search'`.

### The Diagnosis
Qdrant released a major update (SDK v1.17.1+) that deprecated the universal `.search()` method in favor of a modernized `.query_points()` interface for the asynchronous client. Our codebase was still using the legacy dialect.

### The Solution
We performed a **SDK Modernization** in [qdrant.py](file:///d:/ML%20PROJECTS/deepvault/app/infrastructure/stores/qdrant.py):
- Replaced `.search()` with `.query_points()`.
- Synchronized point selection logic with modern Pydantic-based filters.

---

## 🏗️ Failure Vector 2: Serialization Friction
### The Problem
Even after retrieval was fixed, the API returned `500` errors during final response assembly.

### The Diagnosis
Two issues were discovered via our "Red Alert" logging:
1. **Model Mismatch**: The internal `Chunk` model lacked the Pydantic configuration (`from_attributes=True`) required to map its fields to the API's `SourceChunk` response schema.
2. **Metadata Toxicity**: Raw document metadata contained non-serializable objects (like Decimal or nested complex types) from the PDF parser, which caused the standard `json.dumps()` in the logging middleware to crash.

### The Solution
1. **Schema Harmony**: Updated [document.py](file:///d:/ML%20PROJECTS/deepvault/app/core/models/document.py) to support Pydantic attribute mapping.
2. **Metadata Sanitization**: Implemented a recursive `sanitize_metadata` utility in [query.py](file:///d:/ML%20PROJECTS/deepvault/app/services/query.py) to bake all sources into JSON-safe formats before they hit the wire.

---

## 👻 Failure Vector 3: The Ghost Key Hijack
### The Problem
A persistent `401 Unauthorized` error when calling the Groq API, even with a valid `.env` file.

### The Diagnosis (The "Smoking Gun")
During a deep forensic audit of the project infrastructure, we found the **Smoking Gun** on line 8 of [dev.ps1](file:///d:/ML%20PROJECTS/deepvault/dev.ps1):
```powershell
$env:GROQ_API_KEY = "AI ZaSy..." # Invalid Hardcoded Key
```
This hardcoded variable was silently overwriting the valid credentials in the `.env` file on every single startup.

### The Solution
We **Exorcised the Ghost Key** by removing it from the boot script, allowing the project to fall back to its valid `.env` configuration.

---

## 🛡️ Long-Term Hardening
To prevent a repeat of this "Silent Mess," we implemented:
- **Red Alert Logging**: A global exception handler in [main.py](file:///d:/ML%20PROJECTS/deepvault/app/main.py) that force-prints full tracebacks to `stderr`.
- **Atomic Sweep**: An ASCII-only sanitization process for all `.env` configuration to prevent invisible character poisoning.

> [!IMPORTANT]
> **Developer Note**: Always verify [dev.ps1](file:///d:/ML%20PROJECTS/deepvault/dev.ps1) after environment migration to ensure no legacy hardcoded variables have survived.
