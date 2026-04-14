from unittest.mock import MagicMock

import pytest

from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.chunkers.semantic import SemanticChunker
from app.infrastructure.chunkers.sliding import SlidingWindowChunker
from app.infrastructure.chunkers.structure import StructureChunker


def test_fixed_chunker_normal_document(sample_document):
    chunker = FixedWindowChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk(sample_document)

    assert len(chunks) > 0
    # The sample doc is about 98 chars. 50 char chunks with 10 char overlap.
    # Chunk 1: 0-50
    # Chunk 2: 40-90
    # Chunk 3: 80-98
    assert len(chunks) == 3
    assert chunks[0].content == sample_document.content[0:50]


def test_fixed_chunker_short_document():
    doc = Document(id="short-doc", content="Too short.", metadata=DocumentMetadata(source="test"), hash="hash1")
    chunker = FixedWindowChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk(doc)

    assert len(chunks) == 1
    assert chunks[0].content == "Too short."


def test_fixed_chunker_invalid_params():
    with pytest.raises(ValueError):
        FixedWindowChunker(chunk_size=0, chunk_overlap=10)

    with pytest.raises(ValueError):
        FixedWindowChunker(chunk_size=50, chunk_overlap=50)  # overlap must be < size


def test_sliding_chunker_sentence_boundaries():
    text = "This is sentence one. This is sentence two! And sentence three?"
    doc = Document(id="test-doc", content=text, metadata=DocumentMetadata(source="test"), hash="hash1")
    # Window size 25 splits mid-sentence for "This is sentence two!".
    # The chunker should try to expand to the sentence boundary.
    chunker = SlidingWindowChunker(window_size=25, stride=20)
    chunks = chunker.chunk(doc)

    assert len(chunks) > 0


def test_chunk_metadata_propagated(sample_document):
    chunker = FixedWindowChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk(sample_document)

    for chunk in chunks:
        assert chunk.document_id == sample_document.id
        assert chunk.metadata["source"] == sample_document.metadata.source
        assert chunk.metadata["author"] == sample_document.metadata.author


def test_semantic_chunker(mock_embedder):
    doc = Document(
        id="test-doc",
        content="Topic one. Still topic one. Topic two now.",
        metadata=DocumentMetadata(source="test"),
        hash="hash1",
    )
    # Configure the inner model mock used by SemanticChunker
    mock_embedder.model = MagicMock()
    mock_embedder.model.encode.return_value = [[0.1] * 384, [0.1] * 384, [0.1] * 384]

    # The mock embedder returns [0.1]*384 for everything, so similarity is always 1.0 (above threshold)
    # Thus, it should group everything into a single chunk.
    chunker = SemanticChunker(embedder=mock_embedder, similarity_threshold=0.9, min_chunk_size=10)
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1


def test_structure_chunker():
    text = "# Heading 1\nContent 1\n## Heading 2\nContent 2"
    doc = Document(id="test-doc", content=text, metadata=DocumentMetadata(source="test"), hash="hash1")
    chunker = StructureChunker(max_section_size=100, fallback_chunk_size=50, fallback_overlap=10)
    chunks = chunker.chunk(doc)
    assert len(chunks) == 2
    assert "Heading 1" in chunks[0].content
    assert "Heading 2" in chunks[1].content


# --- EDGE CASES ---


def test_fixed_chunker_empty_document():
    doc = Document(id="empty", content="", metadata=DocumentMetadata(source="test"), hash="hash")
    chunker = FixedWindowChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].content == ""


def test_sliding_chunker_no_sentence_breaks():
    doc = Document(id="inf", content="A" * 5000, metadata=DocumentMetadata(source="test"), hash="hash")
    chunker = SlidingWindowChunker(window_size=500, stride=400)
    chunks = chunker.chunk(doc)
    assert len(chunks) > 5
    assert len(chunks[0].content) <= 600  # Will cut off at max window limit (500 + 100 extension)


def test_semantic_chunker_unicode_heavy(mock_embedder):
    text = "Hello 世界. This is a 測試. 🌟 Emoticons help 🚀. Done!"
    doc = Document(id="uni", content=text, metadata=DocumentMetadata(source="test"), hash="hash")

    mock_embedder.model = MagicMock()
    mock_embedder.model.encode.return_value = [[1.0] * 384 for _ in range(4)]

    chunker = SemanticChunker(embedder=mock_embedder, similarity_threshold=0.9, min_chunk_size=5)
    chunks = chunker.chunk(doc)
    assert len(chunks) > 0


def test_structure_chunker_giant_fallback():
    # A huge block of text with only one heading
    text = "# Massive Heading\n" + ("A" * 5000)
    doc = Document(id="giant", content=text, metadata=DocumentMetadata(source="test"), hash="hash")
    chunker = StructureChunker(max_section_size=1500, fallback_chunk_size=500, fallback_overlap=100)
    chunks = chunker.chunk(doc)

    # Needs to be chunked into multiple pieces
    assert len(chunks) >= 10
    # ensure heading is prepended to subsequent chunks
    assert chunks[1].content.startswith("# Massive Heading (cont.)")
