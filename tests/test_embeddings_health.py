import pytest
import asyncio
import numpy as np
from pathlib import Path

from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.embedders.bge import BgeEmbedder

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

@pytest.mark.asyncio
async def test_embedding_variance():
    """Verify that embeddings are not collapsed and have healthy variance."""
    embedder = BgeEmbedder()
    texts = [
        "DeepVault is a RAG system.",
        "The weather is sunny today.",
        "Quantum computing uses qubits.",
        "Machine learning requires data.",
        "The capital of France is Paris."
    ]
    
    embeddings = await embedder.embed_batch(texts)
    embeddings = np.array(embeddings)
    
    # 1. Check for NaNs or Infs
    assert not np.isnan(embeddings).any(), "Embeddings contain NaNs"
    assert not np.isinf(embeddings).any(), "Embeddings contain Infs"
    
    # 2. Check for zero vectors
    magnitudes = np.linalg.norm(embeddings, axis=1)
    assert (magnitudes > 0).all(), "Found zero-magnitude embedding"
    
    # 3. Check for variance (Non-collapse)
    # If variance is extremely low, it means all strings map to the same point
    variance = np.var(embeddings, axis=0).mean()
    assert variance > 1e-5, f"Embedding variance is too low ({variance}), model might be collapsed."

@pytest.mark.asyncio
async def test_semantic_clustering():
    """Verify that similar texts are closer than dissimilar texts."""
    embedder = BgeEmbedder()
    
    base_text = "The machine learning model was trained on a large dataset."
    similar_text = "A massive amount of data was used to train the ML algorithm."
    dissimilar_text = "I like to eat apples and oranges in the morning."
    
    embs = await embedder.embed_batch([base_text, similar_text, dissimilar_text])
    
    sim_pos = cosine_similarity(embs[0], embs[1])
    sim_neg = cosine_similarity(embs[0], embs[2])
    
    assert sim_pos > sim_neg, f"Dissimilar text is closer than similar text! ({sim_pos} <= {sim_neg})"
    assert sim_pos > 0.7, f"Similar texts have unexpectedly low similarity: {sim_pos}"

@pytest.mark.asyncio
async def test_chunk_embedding_drift():
    """Verify that adjacent chunks in a real document have reasonable similarity."""
    embedder = BgeEmbedder()
    chunker = FixedWindowChunker(chunk_size=300, chunk_overlap=50)
    
    content = (
        "This is a long document about the architecture of DeepVault. " * 20
    )
    doc = Document(content=content, metadata=DocumentMetadata(source="test.txt"), hash="h")
    chunks = chunker.chunk(doc)
    
    texts = [c.content for c in chunks[:5]]
    embs = await embedder.embed_batch(texts)
    
    for i in range(len(embs) - 1):
        sim = cosine_similarity(embs[i], embs[i+1])
        # Adjacent chunks should be quite similar because of the overlap and theme
        assert sim > 0.5, f"Adjacent chunks {i} and {i+1} are too dissimilar: {sim}"
