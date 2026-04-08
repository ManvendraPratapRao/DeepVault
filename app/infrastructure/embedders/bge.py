from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.interfaces.embedder import BaseEmbedder
from app.infrastructure.logging.structured import logger


class BgeEmbedder(BaseEmbedder):
    """
    Local implementation of the BaseEmbedder using the BAAI/bge model.
    """

    def __init__(self):
        logger.info(f"Initializing BgeEmbedder with model: {settings.EMBEDDING_MODEL_NAME}")
        # This will download the model (approx 130MB) to your machine on the first run
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

        # BGE models work best with specific instructions for retrieval
        self.instruction = "Represent this sentence for searching relevant passages: "

    async def embed_text(self, text: str) -> list[float]:
        """Embed a query (with instruction prefix)."""
        full_text = f"{self.instruction}{text}"
        embedding = self.model.encode(full_text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed documents (NO instruction prefix)."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        """Return the dimension of the embedding vector."""
        return self.model.get_sentence_embedding_dimension()
