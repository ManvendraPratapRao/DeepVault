from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.interfaces.embedder import BaseEmbedder
from app.infrastructure.logging.structured import logger
from app.services.cache_service import CacheService


class BgeEmbedder(BaseEmbedder):
    """
    Local implementation of the BaseEmbedder using the BAAI/bge model.
    """

    def __init__(self, cache_service: CacheService | None = None):
        logger.info(f"Initializing BgeEmbedder with model: {settings.EMBEDDING_MODEL_NAME}")
        # This will download the model (approx 130MB) to your machine on the first run
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        self.cache_service = cache_service

        # BGE models work best with specific instructions for retrieval
        self.instruction = "Represent this sentence for searching relevant passages: "

    async def embed_text(self, text: str) -> list[float]:
        """Embed a query (with instruction prefix)."""
        full_text = f"{self.instruction}{text}"

        if self.cache_service:
            cached = await self.cache_service.get_cached_embedding(full_text)
            if cached:
                return cached

        embedding = self.model.encode(full_text, convert_to_numpy=True).tolist()

        if self.cache_service:
            await self.cache_service.cache_embedding(full_text, embedding)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed documents (NO instruction prefix) intelligently using cache."""
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        # 1. Check cache for each text
        if self.cache_service:
            for i, text in enumerate(texts):
                cached = await self.cache_service.get_cached_embedding(text)
                if cached:
                    results[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts

        # 2. Compute embeddings for misses
        if uncached_texts:
            new_embeddings = self.model.encode(uncached_texts, convert_to_numpy=True).tolist()

            # 3. Merge back and cache newly computed
            for idx, emb, txt in zip(uncached_indices, new_embeddings, uncached_texts):
                results[idx] = emb
                if self.cache_service:
                    await self.cache_service.cache_embedding(txt, emb)

        return results

    def get_dimension(self) -> int:
        """Return the dimension of the embedding vector."""
        return self.model.get_sentence_embedding_dimension()
