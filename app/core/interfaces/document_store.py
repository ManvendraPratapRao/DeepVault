from abc import ABC, abstractmethod

from app.core.models.document import Document


class BaseDocumentStore(ABC):
    """
    Interface for persisting document metadata and history.
    """

    @abstractmethod
    async def upsert_document(self, document: Document) -> None:
        """Store or update a document's metadata."""
        pass

    @abstractmethod
    async def get_document(self, doc_id: str) -> Document | None:
        """Retrieve document details by ID."""
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str) -> None:
        """Remove a document and its associated metadata."""
        pass

    @abstractmethod
    async def list_documents(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List all documents in the store."""
        pass
