import asyncio
import hashlib
import time
from pathlib import Path

from app.core.exceptions import DuplicateDocumentError, IngestionError
from app.core.interfaces.chunker import BaseChunker
from app.core.interfaces.document_store import BaseDocumentStore
from app.core.interfaces.embedder import BaseEmbedder
from app.core.interfaces.vector_store import BaseVectorStore
from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.logging.structured import logger


class IngestionService:
    """
    Orchestrator for the document ingestion pipeline.
    Coordinates between chunking, embedding, and storage.
    """

    def __init__(
        self,
        chunker: BaseChunker,
        embedder: BaseEmbedder,
        doc_store: BaseDocumentStore,
        vector_store: BaseVectorStore,
    ):
        self.chunker = chunker
        self.embedder = embedder
        self.doc_store = doc_store
        self.vector_store = vector_store

    async def ingest_text(
        self, content: str, source: str, author: str | None = None, extra_metadata: dict | None = None
    ) -> Document:
        """
        The core ingestion logic: Hash -> Chunk -> Embed -> Store (SQL + Vector).
        """
        start_time = time.perf_counter()
        extra_metadata = extra_metadata or {}

        # 1. Compute SHA-256 hash combined with strategy for logical separation
        strategy = getattr(self.chunker, "strategy_name", "unknown")
        unique_string = f"{strategy}_{content}"
        doc_hash = hashlib.sha256(unique_string.encode()).hexdigest()

        # 2. Check for duplicates (Production Safety)
        existing_doc = await self.doc_store.get_document(doc_hash)
        if existing_doc:
            raise DuplicateDocumentError(f"Document with hash {doc_hash} already exists.", detail={"source": source})

        # 3. Build Document Object
        metadata = DocumentMetadata(source=source, author=author, chunking_strategy=strategy, **extra_metadata)
        doc = Document(content=content, hash=doc_hash, metadata=metadata)

        # 4. Chunk it (Offload CPU-heavy task to a thread to keep the API responsive)
        chunks = await asyncio.to_thread(self.chunker.chunk, doc)

        # 5. Embed chunks in batch
        chunk_contents = [c.content for c in chunks]
        embeddings = await self.embedder.embed_batch(chunk_contents)

        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]

        # 6. Store in both databases (The "Double Write")
        # We store metadata in SQLite first, then chunks in Qdrant
        await self.doc_store.upsert_document(doc)
        await self.vector_store.upsert_chunks(chunks)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Successfully ingested document: {source}",
            extra={
                "extra_fields": {
                    "num_chunks": len(chunks),
                    "latency_ms": latency_ms,
                    "doc_id": doc.id,
                }
            },
        )

        return doc

    async def ingest_file(self, file_path: Path) -> Document:
        """Reads a file (Markdown, Text, or PDF) and delegates to ingest_text."""
        if not file_path.exists():
            raise IngestionError(f"File not found: {file_path}")
        suffix = file_path.suffix.lower()

        try:
            if suffix in [".md", ".txt"]:
                content = file_path.read_text(encoding="utf-8")

            elif suffix == ".pdf":
                import fitz

                content = ""
                with fitz.open(file_path) as doc:
                    for page in doc:
                        content += page.get_text()

                if not content.strip():
                    raise IngestionError(f"PDF file {file_path.name} appears to be empty or image-only (no OCR).")

            else:
                raise IngestionError(f"Unsupported file type: {suffix}")
            # Hand off the extracted text to our core ingestion method
            return await self.ingest_text(content=content, source=file_path.name)

        except Exception as e:
            if isinstance(e, (IngestionError, DuplicateDocumentError)):
                raise
            raise IngestionError(f"Failed to process {file_path.name}: {str(e)}") from e

    async def ingest_directory(self, dir_path: Path) -> list[tuple[Document, Exception | None]]:
        """
        Batch processes an entire directory.
        Returns a list of (Document, Error) so one failure doesn't stop the whole job.
        """
        results = []
        # Support common text formats
        files = [f for f in dir_path.glob("**/*") if f.suffix.lower() in [".md", ".txt"]]

        total = len(files)
        logger.info(f"Starting batch ingestion for {total} files in {dir_path}")

        for i, file_path in enumerate(files):
            try:
                doc = await self.ingest_file(file_path)
                results.append((doc, None))
                logger.info(f"[{i + 1}/{total}] Ingested: {file_path.name}")
            except Exception as e:
                results.append((None, e))
                logger.error(f"[{i + 1}/{total}] Failed: {file_path.name} - {str(e)}")

        return results
