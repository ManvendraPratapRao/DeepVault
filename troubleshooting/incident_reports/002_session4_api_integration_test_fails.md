# Incident Report: API Integration Test Failures in Session 4

**Date:** April 8, 2026
**Component:** Integration Tests (`test_api.py`, `test_query_service.py`)

## What Happened
After finalizing the unit tests for chunkers and the ingestion service, we wrote tests for the Query Service and integrated testing for the FastAPI routes using `httpx.AsyncClient`. Upon running the full integration suite, we experienced multiple cascading failures tied to asynchronous context scopes, FastAPI router mounting logic, and persistent local storage locks. We recorded 5 failures and 3 passes initially.

## The Failures & Root Causes

### 1. `test_ask_returns_response`
**Error:** `AssertionError: expected await not found.`
**Root Cause:** The test initialized a `QueryAPIRequest` with `top_k=3` and asserted that `mock_retriever.retrieve` was called with `top_k=3`. However, the implementation inside `QueryService.ask()` strictly invoked retrieval with a hardcoded `top_k=5`. The assertion failed due to this parameter mismatch.

### 2. `test_list_documents_pagination`
**Error:** `AttributeError: 'Document' object has no attribute 'version'`
**Root Cause:** Inside `app/api/v1/routes/documents.py`, when mapping our core `Document` object to the external `DocumentSummary` response schema, the code attempted to access `d.version`. However, the Pydantic `version` attribute physically resides inside the `DocumentMetadata` sub-model, not on the root `Document` parent object.

### 3. All API Tests (Qdrant Locking)
**Error:** `RuntimeError: Storage folder qdrant_storage is already accessed`
**Root Cause:** We run a persistent backend server process (`uv run python main.py`) during development. Our test `test_client` fixture correctly mocked `app.main.initialize_all` to avoid hitting actual databases. However, because our Qdrant vector store instantiates the `AsyncQdrantClient(path="qdrant_storage")` immediately inside `__init__`, simply parsing the module or the `get_vector_store` dependency caused Qdrant to attempt a filesystem lock. Since the background server already held this lock, standard test initialization crashed.

### 4. Dependency Overrides Ignored
**Error:** `RuntimeError: SqliteDocumentStore is not initialized. Call await store.initialize() first.`
**Root Cause:** We explicitly injected mocked services via `app.dependency_overrides[get_ingestion_service] = ...`. However, in `app/main.py`, the routing structure was defined using:
```python
app.mount("/api/v1", api_router)
app.include_router(api_router, prefix="/api/v1")
```
Mounting an `APIRouter` creates an independent sub-application wrapper that strictly isolates itself from the parent `app`'s runtime state. Consequently, the API tests routed through the mounted app entirely bypassed our intended `dependency_overrides`, causing them to hit the actual uninitialized business logic dependencies (and thus failing the DB checks).

## How We Solved It

1. **Parameter Alignment:** Updated `test_query_service.py` to assert that retrieval was called with `top_k=5` instead of `3`, matching production configuration.
2. **Data Model Paths:** Changed the problematic assignment in `documents.py` from `d.version` to `d.metadata.version` for correct serialization.
3. **Qdrant Patching:** Updated `test_api.py` to natively patch the `AsyncQdrantClient` globally (`patch("app.infrastructure.stores.qdrant.AsyncQdrantClient")`). This successfully prevents tests from touching the hard drive or conflicting with our active terminal server.
4. **Router Fixing:** Removed the invalid `app.mount("/api/v1", api_router)` statement from `app/main.py`, leaving only `app.include_router()`. This ensured the routing layer remained a part of the core FastAPI app tree, faithfully honoring our injected memory mocks.

## Verification
Following the fixes, executing `uv run pytest -v --tb=short` resolved all assertions and lock allocations beautifully. The entire suite executed perfectly in ~12 seconds.
