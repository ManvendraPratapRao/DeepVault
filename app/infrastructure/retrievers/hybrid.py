import asyncio

from app.core.interfaces.retriever import BaseRetriever
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger


class HybridRetriever(BaseRetriever):
    """
    Combines Vector Semantic Search and BM25 Keyword Search using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        vector_retriever: BaseRetriever,
        bm25_retriever: BaseRetriever,
        rrf_k: int = 60,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
    ):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict | None = None, collection_name: str | None = None
    ) -> list[Chunk]:

        # We fetch more chunks to ensure a good intersection
        fetch_k = top_k * 4

        try:
            vector_task = asyncio.create_task(self.vector_retriever.retrieve(query, fetch_k, filters, collection_name))
            bm25_task = asyncio.create_task(self.bm25_retriever.retrieve(query, fetch_k, filters, collection_name))

            # Parallel independent retrieval
            vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)

            logger.info(f"Hybrid Retrieval: Found {len(vector_results)} Vector hits and {len(bm25_results)} BM25 hits.")

        except Exception as e:
            logger.error(f"Hybrid retrieval failed entirely: {e}")
            raise

        # Reciprocal Rank Fusion
        fused_scores: dict[str, float] = {}
        chunk_map: dict[str, Chunk] = {}

        # Process Vector Results
        for rank, chunk in enumerate(vector_results):
            if chunk.id not in chunk_map:
                chunk_map[chunk.id] = chunk
            if chunk.id not in fused_scores:
                fused_scores[chunk.id] = 0.0

            # RRF Formula
            fused_scores[chunk.id] += self.vector_weight * (1.0 / (self.rrf_k + rank + 1))

        # Process BM25 Results
        for rank, chunk in enumerate(bm25_results):
            if chunk.id not in chunk_map:
                chunk_map[chunk.id] = chunk
            if chunk.id not in fused_scores:
                fused_scores[chunk.id] = 0.0

            fused_scores[chunk.id] += self.bm25_weight * (1.0 / (self.rrf_k + rank + 1))

        # Sort by the Fused Score descending
        sorted_chunks = sorted(chunk_map.values(), key=lambda c: fused_scores[c.id], reverse=True)

        # Normalize score to [0, 1] range for UI consistency (Max theoretical RRF is at rank 0 for both)
        max_rrf_score = (self.vector_weight + self.bm25_weight) / (self.rrf_k + 1)

        final_chunks = []
        for chunk in sorted_chunks[:top_k]:
            chunk.score = fused_scores[chunk.id] / max_rrf_score
            final_chunks.append(chunk)

        return final_chunks
