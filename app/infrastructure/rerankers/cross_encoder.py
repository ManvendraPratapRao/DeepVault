import asyncio

from sentence_transformers import CrossEncoder

from app.core.interfaces.reranker import BaseReranker
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger


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
            # ms-marco models output raw logits, we don't necessarily need sigmoid
            scores = await asyncio.to_thread(self.encoder.predict, pairs)

            # Pair each chunk with its new score
            scored_chunks = list(zip(chunks, scores, strict=False))

            # Sort descending by score
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            logger.info(f"Cross-Encoder successfully reranked {len(chunks)} chunks.")

            # Update chunks with their new precise scores and return top_k
            final_chunks = []
            for chunk, score in scored_chunks[:top_k]:
                chunk.score = float(score)  # Convert numpy float to native float
                final_chunks.append(chunk)
                
            return final_chunks

        except Exception as e:
            logger.error(f"Cross-Encoder reranking failed: {e}")
            # Fall fail-open: return default retrieved chunks
            return chunks[:top_k]
