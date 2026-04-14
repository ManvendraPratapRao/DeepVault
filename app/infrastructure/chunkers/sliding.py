import re
import uuid

from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Chunk, Document


class SlidingWindowChunker(BaseChunker):
    """
    An advanced chunker that slides a window across the text.
    It attempts to find natural sentence boundaries ('.', '!', '?')
    to avoid cutting sentences in half.
    """

    def __init__(self, window_size: int = 600, stride: int = 480):
        self.strategy_name = "sliding"
        self.window_size = window_size
        self.stride = stride

    def chunk(self, document: Document) -> list[Chunk]:
        """
        Implementation of the sliding-window logic.
        """
        chunks = []
        text = document.content
        start = 0
        index = 0

        overlap = self.window_size - self.stride
        if overlap < 0:
            overlap = 0

        while start < len(text):
            # 1. Expand the END to a sentence boundary
            end = min(start + self.window_size, len(text))
            if end < len(text):
                lookahead = text[end : end + 100]
                sentence_break = re.search(r"[.!?]\s+", lookahead)
                if sentence_break:
                    effective_end = end + sentence_break.end()
                else:
                    effective_end = end
            else:
                effective_end = end

            chunk_text = text[start:effective_end].strip()

            if chunk_text:
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document.id,
                        content=chunk_text,
                        chunk_index=index,
                        metadata=document.metadata.model_dump(),
                    )
                )

            # 2. Advance START dynamically for the next chunk
            if effective_end >= len(text):
                break

            target_next_start = max(start + 1, effective_end - overlap)

            # Find a sentence boundary near the target start point
            if target_next_start < effective_end:
                lookahead_start = text[target_next_start : target_next_start + 150]
                start_boundary = re.search(r"[.!?]\s+", lookahead_start)

                if start_boundary and (target_next_start + start_boundary.end() < effective_end):
                    start = target_next_start + start_boundary.end()
                else:
                    start = target_next_start
            else:
                start = target_next_start

            index += 1

        return chunks
