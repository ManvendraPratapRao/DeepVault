from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings
from app.core.interfaces.vector_store import BaseVectorStore
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger


class QdrantVectorStore(BaseVectorStore):
    """
    Qdrant implementation of the Vector Store.
    Uses 'Local Path' storage for persistent disk-based indexing.
    """

    def __init__(self, collection_name: str = None):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        # Use local path for persistence without Docker
        self.client = AsyncQdrantClient(path="qdrant_storage")

    async def initialize(self, vector_size: int):
        """Creates the collection with the correct vector dimensions."""
        collections = await self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

        if not exists:
            logger.info(f"Creating Qdrant collection: {self.collection_name} (Size: {vector_size})")
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            logger.info(f"Qdrant collection {self.collection_name} already exists.")

    async def close(self):
        """Gracefully closes the Qdrant client connection."""
        await self.client.close()
        logger.info("Qdrant Vector Store connection closed.")

    async def upsert_chunks(self, chunks: list[Chunk]) -> None:
        """Converts Chunks into Qdrant Points and uploads them."""
        points = []
        for chunk in chunks:
            if not chunk.embedding:
                continue

            # Qdrant accepts UUID strings — ensure consistent formatting
            points.append(
                PointStruct(
                    id=chunk.id,
                    vector=chunk.embedding,
                    payload={
                        "document_id": chunk.document_id,
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        **chunk.metadata,
                    },
                )
            )

        if not points:
            logger.warning("upsert_chunks called but no chunks had embeddings. Nothing upserted.")
            return

        await self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} points to Qdrant.")

    async def search(
        self, query_vector: list[float], top_k: int = 5, filters: dict | None = None
    ) -> list[Chunk]:
        """Searches for the nearest neighbors using the modern query_points API."""

        # Build Qdrant filter if filter dict is provided
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=conditions)

        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        # In the new API, results are in .points
        return [
            Chunk(
                id=str(point.id),
                document_id=point.payload["document_id"],
                content=point.payload["content"],
                chunk_index=point.payload["chunk_index"],
                metadata={
                    k: v
                    for k, v in point.payload.items()
                    if k not in ["document_id", "content", "chunk_index"]
                },
            )
            for point in results.points
        ]

    async def delete_by_doc_id(self, doc_id: str) -> None:
        """Filters by document_id and deletes the associated points."""
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
            ),
        )
        logger.info(f"Deleted all points for document: {doc_id}")
