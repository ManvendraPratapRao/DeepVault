from app.core.exceptions import DocumentNotFoundError
from app.core.interfaces.document_store import BaseDocumentStore
from app.core.interfaces.vector_store import BaseVectorStore
from app.core.models.document import Document
from app.infrastructure.logging.structured import logger


class DocumentService:
    """
    Service for managing stored documents and their metadata.
    Provides a high-level API for listing, retrieving, and deleting documents.
    """

    def __init__(self, doc_store: BaseDocumentStore, vector_store: BaseVectorStore):
        self.doc_store = doc_store
        self.vector_store = vector_store

    async def get_document(self, doc_id: str) -> Document:
        """
        Retrieves a single document by its ID (the SHA-256 hash).
        """
        doc = await self.doc_store.get_document(doc_id)
        if not doc:
            raise DocumentNotFoundError(f"Document with ID {doc_id} not found.")
        return doc

    async def list_documents(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """
        Returns a paginated list of all indexed documents.
        Essential for your "Archive" view or internal data audit.
        """
        return await self.doc_store.list_documents(limit=limit, offset=offset)

    async def delete_document(self, doc_id: str) -> None:
        """
        The "Atomic Delete": Removes metadata from SQLite AND vectors from Qdrant.
        """
        logger.info(f"Initiating full deletion for document: {doc_id}")

        # 1. Delete chunks from the Vector Store first (higher risk of orphan vectors)
        await self.vector_store.delete_by_doc_id(doc_id)

        # 2. Delete the document metadata record from SQLite
        await self.doc_store.delete_document(doc_id)

        logger.info(f"Successfully deleted document and all associated chunks: {doc_id}")
