import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from app.services.ingestion import IngestionService
from app.core.exceptions import DuplicateDocumentError, IngestionError
from app.core.models.document import DocumentMetadata, Document, Chunk

@pytest.fixture
def mock_chunker(sample_chunks):
    chunker = MagicMock()
    chunker.chunk.return_value = sample_chunks
    return chunker

@pytest.fixture
def ingestion_service(mock_chunker, mock_embedder, mock_doc_store, mock_vector_store):
    return IngestionService(
        chunker=mock_chunker,
        embedder=mock_embedder,
        doc_store=mock_doc_store,
        vector_store=mock_vector_store
    )

@pytest.mark.asyncio
async def test_ingest_text_success(ingestion_service, mock_doc_store, mock_vector_store, mock_embedder):
    mock_doc_store.get_document.return_value = None # Ensure it's not a duplicate
    
    doc = await ingestion_service.ingest_text(
        content="Test content",
        source="test.txt",
        author="Unit Test"
    )
    
    assert doc is not None
    assert doc.content == "Test content"
    assert doc.metadata.source == "test.txt"
    
    # Check that it stored the doc and the chunks
    mock_doc_store.upsert_document.assert_awaited_once()
    mock_vector_store.upsert_chunks.assert_awaited_once()
    mock_embedder.embed_batch.assert_awaited_once()

@pytest.mark.asyncio
async def test_ingest_duplicate_raises(ingestion_service, mock_doc_store):
    # Setup mock to return an existing document
    mock_doc_store.get_document.return_value = Document(
        id="existing-id", content="test", metadata=DocumentMetadata(source="test"), hash="testhash"
    )
    
    with pytest.raises(DuplicateDocumentError):
        await ingestion_service.ingest_text("Test content", "test.txt")

@pytest.mark.asyncio
async def test_ingest_file_md(ingestion_service, tmp_path, mock_doc_store):
    mock_doc_store.get_document.return_value = None
    
    md_file = tmp_path / "test.md"
    md_file.write_text("Markdown content")
    
    doc = await ingestion_service.ingest_file(md_file)
    assert doc.content == "Markdown content"
    assert doc.metadata.source == "test.md"

@pytest.mark.asyncio
async def test_ingest_file_unsupported_type(ingestion_service, tmp_path):
    exe_file = tmp_path / "test.exe"
    exe_file.write_text("binary blob")
    
    with pytest.raises(IngestionError, match="Unsupported file type"):
        await ingestion_service.ingest_file(exe_file)

@pytest.mark.asyncio
async def test_ingest_directory(ingestion_service, tmp_path, mock_doc_store):
    mock_doc_store.get_document.return_value = None
    
    (tmp_path / "file1.md").write_text("content 1")
    (tmp_path / "file2.txt").write_text("content 2")
    (tmp_path / "file3.exe").write_text("binary") # should be skipped by glob filter (.md, .txt)
    
    results = await ingestion_service.ingest_directory(tmp_path)
    
    # 2 text files should be processed successfully
    assert len(results) == 2
    successes = [r for r, e in results if e is None]
    assert len(successes) == 2
