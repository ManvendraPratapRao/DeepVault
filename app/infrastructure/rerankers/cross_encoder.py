import asyncio
import math
from typing import cast

import numpy as np

from sentence_transformers import CrossEncoder

from app.core.interfaces.reranker import BaseReranker
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger


def _sigmoid(logit: float) -> float:
    """Helper to normalise logits to [0, 1]."""
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_val = math.exp(logit)
    return exp_val / (1.0 + exp_val)


class CrossEncoderReranker(BaseReranker):
    """
    Highly precise semantic reranker using a Cross-Encoder.
    Reads both the query and the chunk simultaneously through self-attention layers.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        logger.info(f"Loading Cross-Encoder Reranker model: {model_name}")
        # The cross encoder loads synchronously into memory/device
        self.encoder = CrossEncoder(model_name)

    async def rerank(self, query: str, chunks: list[Chunk], top_k: int = 5) -> list[Chunk]:
        if not chunks:
            return []

        # Reranker struggles with over 100 docs usually, safe limit is 50.
        if len(chunks) > 100:
            logger.warning(f"Reranking {len(chunks)} chunks is very expensive. Truncating to 100.")
            chunks = chunks[:100]

        # Structure input for the cross encoder: List of (query, chunk_text)
        pairs = [[query, chunk.content] for chunk in chunks]

        try:
            # We predict synchronously, offload to thread to prevent blocking the async loop
            _raw = await asyncio.to_thread(self.encoder.predict, pairs)
            # Cast to ndarray: sentence_transformers' type stubs declare a broad
            # return union (Tensor | ndarray | list[Tensor]) that confuses pyright,
            # but predict() always returns a numpy array or scalar at runtime.
            raw_scores = cast(np.ndarray, _raw)

            # BUG FIX: encoder.predict() returns a 0-d numpy scalar when given a
            # single pair (e.g. np.float32(9.84)). A 0-d array is not iterable,
            # causing `zip(chunks, scores)` to raise TypeError. atleast_1d()
            # guarantees we always have a 1-d array regardless of input count.
            scores = np.atleast_1d(raw_scores)

            # Pair each chunk with its normalised [0, 1] probability score
            scored_chunks = [(chunk, _sigmoid(float(s))) for chunk, s in zip(chunks, scores)]

            # Sort descending by normalised probability
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            logger.info(f"Cross-Encoder successfully reranked {len(chunks)} chunks.")

            # Assign final scores and return top_k
            final_chunks = []
            for chunk, prob in scored_chunks[:top_k]:
                chunk.score = (prob)
                final_chunks.append(chunk)

            return final_chunks

        except Exception as e:
            logger.error(f"Cross-Encoder reranking failed: {e}")
            # Fall fail-open: return default retrieved chunks
            return chunks[:top_k]
