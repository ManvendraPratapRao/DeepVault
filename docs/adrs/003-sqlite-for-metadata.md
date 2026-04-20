# ADR-003: Metadata Store — SQLite via aiosqlite

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Manvendra Pratap Rao

---

## Context

DeepVault needs a metadata store to track ingested documents. Each document record needs to store:
- A unique document ID (UUID).
- A SHA-256 content hash (for duplicate detection).
- Source filename, title, author, file type.
- Ingestion timestamp.

This store has two primary use cases:
1. **Duplicate detection** — Before ingesting a document, check if its hash already exists.
2. **Document listing** — Return a list of all ingested documents via the `/documents` endpoint.

The store is write-once/read-many: documents are ingested once and rarely deleted. Query patterns are simple (lookup by hash, list all).

Candidates considered: **SQLite (aiosqlite)**, **PostgreSQL (asyncpg)**, **MongoDB**, **plain JSON files**.

---

## Decision

**Use SQLite** with the `aiosqlite` async wrapper for Phase 1. Plan a PostgreSQL migration in Phase 4.

---

## Evaluation

### SQLite + aiosqlite

| Criterion | Assessment |
|-----------|------------|
| Setup complexity | ✅ Zero. No server, no Docker, no credentials. File auto-created on first run. |
| Async support | ✅ `aiosqlite` wraps SQLite with `asyncio`-compatible `async/await`. |
| Performance | ✅ Sufficient for Phase 1 (hundreds to low thousands of documents). |
| Data durability | ✅ Committed to disk. WAL mode enabled for concurrent readers. |
| Schema migrations | ✅ Simple `CREATE TABLE IF NOT EXISTS` is sufficient for this schema. |
| Query complexity | ✅ Simple lookups by hash and UUID are trivially fast for SQLite. |
| Portability | ✅ The `.db` file is self-contained and easily backed up. |

### PostgreSQL + asyncpg

| Criterion | Assessment |
|-----------|------------|
| Setup complexity | ⚠️ Requires a running PostgreSQL server (Docker or managed). |
| Async support | ✅ `asyncpg` is the gold standard for async PostgreSQL. |
| Performance | ✅ Scales to millions of documents with connection pooling. |
| Value in Phase 1 | ❌ Overkill. Phase 1 corpus is <1,000 documents. PostgreSQL's strengths don't apply. |

**Deferred to Phase 4:** PostgreSQL migration is planned when the document store needs to handle concurrent writes from multiple API workers (Gunicorn/Uvicorn multi-process).

### MongoDB

| Criterion | Assessment |
|-----------|------------|
| Schema flexibility | ✅ Document-style storage fits the metadata model. |
| Async support | ✅ `motor` async driver. |
| Operational overhead | ❌ Requires a running MongoDB server. |
| Value in Phase 1 | ❌ Unnecessary for a fixed-schema, low-volume metadata store. |

**Rejected:** No advantage over SQLite for fixed-schema metadata at this scale.

### JSON Files

| Criterion | Assessment |
|-----------|------------|
| Setup complexity | ✅ Zero. |
| Concurrent access | ❌ Race conditions with multiple writers. |
| Query performance | ❌ O(n) scan for duplicate detection as corpus grows. |

**Rejected:** Not safe for concurrent async access.

---

## Consequences

**Positive:**
- Zero infrastructure setup. The database is auto-initialized on first run.
- The `BaseDocumentStore` ABC makes it trivial to swap SQLite for PostgreSQL later.
- `aiosqlite` integrates cleanly with FastAPI's async request handlers.

**Negative:**
- SQLite has limited concurrency (multiple writers will serialize). Acceptable for Phase 1's single-worker deployment.
- Does not support connection pooling. Each connection is per-request.
- SQLite file must be accessible on the same filesystem as the API process — complicates multi-node deployments.

---

## Implementation Notes

- Database file: `deepvault.db` (configurable via `SQLITE_DB_PATH` in settings).
- Table is created with `CREATE TABLE IF NOT EXISTS` at startup in `SqliteDocumentStore.initialize()`.
- Duplicate detection uses `SELECT id FROM documents WHERE hash = ?` — queries by hash, not by primary key.
- The `SqliteDocumentStore` implements `BaseDocumentStore` (`app/core/interfaces/document_store.py`).
- Migration path to PostgreSQL (Phase 4): create `PostgresDocumentStore` implementing the same ABC. No `IngestionService` changes required.
