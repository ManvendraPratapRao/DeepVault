import re
import uuid

import numpy as np

from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Chunk, Document
from app.infrastructure.logging.structured import logger


class SemanticChunker(BaseChunker):
    """
    Groups sentences by embedding similarity. When the cosine similarity
    between consecutive sentences drops below a threshold, a new chunk begins.

    This is the "smartest" chunker — it respects meaning boundaries.
    Trade-off: Slower ingestion (requires embedding every sentence).
    """

    def __init__(self, embedder, similarity_threshold: float = 0.85, min_chunk_size: int = 100):
        self.strategy_name = "semantic"
        """
        Args:
            embedder: A BgeEmbedder instance. We use its internal model for sync encoding.
            similarity_threshold: Cosine sim below this starts a new chunk (0.0 to 1.0).
            min_chunk_size: Minimum characters per chunk. Tiny chunks get merged with neighbors.
        """
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences using regex."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk(self, document: Document) -> list[Chunk]:
        """
        1. Split into sentences
        2. Embed each sentence (sync, via the underlying SentenceTransformer model)
        3. Walk through: when similarity between consecutive sentences drops, start new chunk
        """
        sentences = self._split_sentences(document.content)

        # Edge cases: empty or single-sentence documents
        if len(sentences) <= 1:
            return [
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=document.content,
                    chunk_index=0,
                    metadata=document.metadata.model_dump(),
                )
            ]

        # Embed all sentences synchronously (this runs inside asyncio.to_thread)
        embeddings = self.embedder.model.encode(sentences, convert_to_numpy=True, show_progress_bar=False)

        # Vectorized similarity calculation: compute cosine sim between consecutive sentences
        # Shape of embeddings: (num_sentences, dim)
        norms = np.linalg.norm(embeddings, axis=1)
        # Avoid division by zero
        norms[norms == 0] = 1e-9
        
        # Dot product of consecutive vectors
        # embeddings[:-1] is sentences [0, n-1], embeddings[1:] is sentences [1, n]
        dots = np.sum(embeddings[:-1] * embeddings[1:], axis=1)
        similarities = dots / (norms[:-1] * norms[1:])

        # Group sentences by similarity
        groups: list[list[str]] = [[sentences[0]]]

        for i, sim in enumerate(similarities):
            # i corresponds to the similarity between sentences[i] and sentences[i+1]
            if sim < self.similarity_threshold:
                # Topic shifted — start a new group
                groups.append([sentences[i + 1]])
            else:
                # Same topic — keep grouping
                groups[-1].append(sentences[i + 1])

        # Merge tiny groups into their neighbors
        merged_groups: list[list[str]] = []
        for group in groups:
            text = " ".join(group)
            if merged_groups and len(text) < self.min_chunk_size:
                # Too small, merge with the previous group
                merged_groups[-1].extend(group)
            else:
                merged_groups.append(group)

        # Build Chunk objects
        chunks = []
        for idx, group in enumerate(merged_groups):
            chunk_text = " ".join(group)
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=idx,
                    metadata=document.metadata.model_dump(),
                )
            )

        logger.info(
            f"Semantic chunker created {len(chunks)} chunks from {len(sentences)} sentences",
            extra={"extra_fields": {"threshold": self.similarity_threshold}},
        )
        return chunks
