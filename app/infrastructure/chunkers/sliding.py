import uuid
import re
from typing import List
from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Document, Chunk

class SlidingWindowChunker(BaseChunker):
    """
    An advanced chunker that slides a window across the text. 
    It attempts to find natural sentence boundaries ('.', '!', '?') 
    to avoid cutting sentences in half.
    """
    def __init__(self, window_size: int = 1200, stride: int = 400):
        self.window_size = window_size
        self.stride = stride

    def chunk(self, document: Document) -> List[Chunk]:
        """
        Implementation of the sliding-window logic.
        """
        chunks = []
        text = document.content
        start = 0
        index = 0

        while start < len(text):
            # 1. Define the ideal window
            end = min(start + self.window_size, len(text))
            
            # 2. Try to expand/shrink slightly to hit a sentence end (grace period of 100 chars)
            lookahead = text[end : end + 100]
            sentence_break = re.search(r'[.!?]\s', lookahead)
            
            if sentence_break:
                effective_end = end + sentence_break.end()
            else:
                effective_end = end

            chunk_text = text[start:effective_end]
            
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=index,
                    metadata=document.metadata.model_dump()
                )
            )
            
            # 3. Slide the start forward by the stride
            start += self.stride
            index += 1
            
            # Prevent infinite loops if stride is 0 or negative
            if self.stride <= 0:
                break
                
        return chunks
