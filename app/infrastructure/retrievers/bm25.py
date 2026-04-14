import asyncio
import re

from rank_bm25 import BM25Okapi
from qdrant_client import AsyncQdrantClient

from app.core.interfaces.retriever import BaseRetriever
from app.core.models.document import Chunk, DocumentMetadata
from app.infrastructure.logging.structured import logger


class BM25Retriever(BaseRetriever):
    """
    Retrieves documents using exact keyword relevance (BM25).
    Dynamically loads all chunks from Qdrant upon initialization.
    """

    def __init__(self, qdrant_client: AsyncQdrantClient):
        self.client = qdrant_client
        self._indexes: dict[str, BM25Okapi] = {}
        self._corpus: dict[str, list[Chunk]] = {}
        self._initialization_lock = asyncio.Lock()

    def _tokenize(self, text: str) -> list[str]:
        # Basic lowercase tokenization by word boundary for BM25
        return re.sub(r"[^\w\s]", "", str(text).lower()).split()

    async def initialize(self, collection_name: str) -> None:
        """
        Pulls all chunks from a given collection to build the BM25 index in memory.
        """
        if collection_name in self._indexes:
            return

        async with self._initialization_lock:
            # Double checked locking
            if collection_name in self._indexes:
                return

            logger.info(f"Building BM25 Index for collection '{collection_name}'...")
            try:
                # We need all chunks to construct the inverted index
                chunks = []
                offset = None
                while True:
                    records, next_offset = await self.client.scroll(
                        collection_name=collection_name, 
                        limit=1000, 
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    for record in records:
                        metadata_dict = record.payload.get("metadata", {}) if record.payload else {}
                        meta = DocumentMetadata(**metadata_dict) if metadata_dict else DocumentMetadata(source="unknown")
                        
                        chunk = Chunk(
                            id=str(record.id),
                            document_id=record.payload.get("document_id", "unknown") if record.payload else "unknown",
                            content=record.payload.get("content", "") if record.payload else "",
                            chunk_index=record.payload.get("chunk_index", 0) if record.payload else 0,
                            metadata=meta.model_dump()
                        )
                        chunks.append(chunk)

                    if next_offset is None:
                        break
                    offset = next_offset

                # Tokenize corpus and initialize BM25
                tokenized_corpus = [self._tokenize(c.content) for c in chunks]
                
                # If there are no chunks yet, we provide an empty dummy setup
                if not tokenized_corpus:
                    self._indexes[collection_name] = BM25Okapi([["dummy"]])
                    self._corpus[collection_name] = []
                    logger.warning(f"BM25 Index for '{collection_name}' initialized with empty corpus.")
                else:
                    self._indexes[collection_name] = BM25Okapi(tokenized_corpus)
                    self._corpus[collection_name] = chunks
                    logger.info(f"BM25 Index for '{collection_name}' ready. Bound {len(chunks)} chunks.")

            except Exception as e:
                logger.error(f"Failed to initialize BM25 index for {collection_name}: {e}")
                raise

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict | None = None, collection_name: str | None = None
    ) -> list[Chunk]:
        
        if not collection_name:
            raise ValueError("BM25Retriever requires a specific collection name.")

        # Ensure index exists
        if collection_name not in self._indexes:
            await self.initialize(collection_name)

        if not self._corpus[collection_name]:
            return []

        tokenized_query = self._tokenize(query)
        # We fetch extra chunks for safety since we're returning chunks
        top_n = self._indexes[collection_name].get_top_n(tokenized_query, self._corpus[collection_name], n=top_k*2)

        # Basic filtering map
        results: list[Chunk] = []
        for chunk in top_n:
            if len(results) >= top_k:
                break
                
            if filters:
                # Handle rudimentary document_id filtering for now
                if "document_id" in filters and chunk.document_id != filters["document_id"]:
                    continue
            results.append(chunk)

        # Inject BM25 score proxy (we recalculate just for metadata)
        scores = self._indexes[collection_name].get_scores(tokenized_query)
        # Finding the exact score for chunk is complex with Okapi, we just return the nodes
        return results
