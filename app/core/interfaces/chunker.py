from abc import ABC, abstractmethod
from typing import List
from app.core.models.document import Document, Chunk

class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, document: Document) -> List[Chunk]:
        pass