import json
import aiosqlite
from typing import Optional, List
from app.core.interfaces.document_store import BaseDocumentStore
from app.core.models.document import Document, DocumentMetadata
from app.config import settings
from app.infrastructure.logging.structured import logger

class SqliteDocumentStore(BaseDocumentStore):
    """
    Asynchronous SQLite implementation for document metadata storage.
    Uses a persistent connection to avoid the overhead of reconnecting on every operation.
    """
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Opens a persistent connection and creates tables if needed."""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                hash TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.commit()
        logger.info("SQLite Document Store initialized.", extra={"extra_fields": {"db_path": self.db_path}})

    async def close(self):
        """Gracefully closes the persistent database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("SQLite Document Store connection closed.")

    def _ensure_connected(self):
        """Guard to prevent operations on a closed or uninitialized store."""
        if self._db is None:
            raise RuntimeError("SqliteDocumentStore is not initialized. Call await store.initialize() first.")

    async def upsert_document(self, document: Document) -> None:
        """Stores or updates a document using its ID."""
        self._ensure_connected()
        await self._db.execute(
            "INSERT OR REPLACE INTO documents (id, content, hash, metadata) VALUES (?, ?, ?, ?)",
            (
                document.id,
                document.content,
                document.hash,
                document.metadata.model_dump_json()
            )
        )
        await self._db.commit()

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieves a document by its ID."""
        self._ensure_connected()
        async with self._db.execute(
            "SELECT id, content, hash, metadata FROM documents WHERE id = ?", (doc_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Document(
                    id=row[0],
                    content=row[1],
                    hash=row[2],
                    metadata=DocumentMetadata.model_validate_json(row[3])
                )
        return None

    async def delete_document(self, doc_id: str) -> None:
        """Removes a document from the store."""
        self._ensure_connected()
        await self._db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        await self._db.commit()

    async def list_documents(self, limit: int = 100, offset: int = 0) -> List[Document]:
        """Returns a paginated list of all stored documents."""
        self._ensure_connected()
        async with self._db.execute(
            "SELECT id, content, hash, metadata FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                Document(
                    id=row[0],
                    content=row[1],
                    hash=row[2],
                    metadata=DocumentMetadata.model_validate_json(row[3])
                )
                for row in rows
            ]

