from app.core.interfaces.embedder import BaseEmbedder
from app.core.interfaces.retriever import BaseRetriever
from app.core.interfaces.vector_store import BaseVectorStore
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger


class VectorRetriever(BaseRetriever):
    """
    Standard Vector-based retriever.
    Converts text queries into embeddings and searches the Vector Store.
    """

    def __init__(self, embedder: BaseEmbedder, vector_store: BaseVectorStore):
        """
        Dependency Injection: We pass in an embedder and a vector store.
        This makes the retriever completely independent of the specific
        model or database brand.
        """
        self.embedder = embedder
        self.vector_store = vector_store

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict | None = None
    ) -> list[Chunk]:
        """
        The core retrieval logic:
        1. Embed the query
        2. Search the vector store
        3. Return the results
        """
        logger.info(
            f"Retrieving context for query: {query[:50]}...",
            extra={"extra_fields": {"top_k": top_k}},
        )

        # 1. Turn text into a vector
        query_vector = await self.embedder.embed_text(query)

        # 2. Search the database
        results = await self.vector_store.search(
            query_vector=query_vector, top_k=top_k, filters=filters
        )

        logger.info(f"Found {len(results)} relevant chunks.")
        return results
