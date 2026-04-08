# Incident Report: Unit Test Failures in Session 4

**Date:** April 8, 2026
**Component:** Unit Tests (Chunkers & Ingestion Service)

## What Happened
During Session 4, we implemented unit tests for our 4 chunking strategies (`FixedWindow`, `SlidingWindow`, `Semantic`, and `Structure`) and the `IngestionService`. Upon running the initial test suite, 5 out of 12 tests failed while 7 passed. 

## The Failures & Root Causes

### 1. `test_semantic_chunker`
**Error:** `TypeError: 'coroutine' object is not subscriptable`
**Root Cause:** 
The `SemanticChunker` relies on synchronous embeddings via `embedder.model.encode()` executing inside an `asyncio.to_thread` call in production. In our test mock (`mock_embedder`), we returned a mock embedder, but since we didn't specify the nested `.model.encode()` behavior, it defaulted to returning a coroutine (because `conftest.py` used `AsyncMock`). A coroutine cannot be indexed like a list, causing the failure natively inside the chunking method.

### 2. `test_structure_chunker`
**Error:** `ValueError: chunk_overlap (100) must be less than chunk_size (50), otherwise the window never advances`
**Root Cause:**
The `StructureChunker` has a fallback parameter for non-markdown text (`fallback_overlap=100` by default). The test initialized the chunker as `StructureChunker(max_section_size=100, fallback_chunk_size=50)`. Since the chunk size was reduced to `50` but the overlap defaulted to `100`, the invariant rule in our `FixedWindowChunker` triggered a built-in safety check error (overlap >= chunk size leads to an infinite loop).

### 3. `test_ingest_text_success` and others (`test_ingest_file_md`, `test_ingest_directory`)
**Error:** `IndexError: list index out of range`
**Root Cause:**
In `conftest.py`, the `mock_embedder.embed_batch.return_value` was set to return a list of exactly **2 embeddings**. However, the `sample_chunks` fixture returned **3 literal chunks**. When the IngestionService looped over the chunks to assign the mocked embeddings (`chunk.embedding = embeddings[i]`), it hit an index out of bounds on the 3rd iteration `i=2`.

## How We Solved It

1. **Semantic Mock Fix**: In `test_chunkers.py`, we explicitly mocked the inner `model` behavior using a standard synchronous mock:
   ```python
   mock_embedder.model = MagicMock()
   mock_embedder.model.encode.return_value = [[0.1]*384, [0.1]*384, [0.1]*384]
   ```

2. **Structure Parameter Fix**: In `test_chunkers.py`, we passed the appropriately scoped `fallback_overlap=10` parameter into the initialization:
   ```python
   StructureChunker(max_section_size=100, fallback_chunk_size=50, fallback_overlap=10)
   ```

3. **Array Bounds Fix**: In `conftest.py`, we updated the `mock_embedder` fixture so that the returned batch size exactly matched the chunk array size:
   ```python
   embedder.embed_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
   ```

## Verification
Following these changes, the entire suite of 12 tests was rerun using `uv run pytest tests/unit/test_chunkers.py tests/unit/test_ingestion_service.py -v`. The suite passed with a 100% success rate (12/12 passed).
