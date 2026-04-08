from abc import ABC, abstractmethod

from app.core.models.document import Chunk, Document


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        pass
