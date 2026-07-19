import uuid

from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Chunk, Document
from app.infrastructure.logging.structured import logger


class RecursiveChunker(BaseChunker):
    """
    Recursively splits text using a hierarchy of separators until the chunks are small enough.
    This is the industry standard for chunking general text (e.g., LangChain's RecursiveCharacterTextSplitter).
    It tries to keep paragraphs together first, then sentences, then words.
    """

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ):
        self.strategy_name = "recursive"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # Default hierarchy: Paragraphs -> Sentences -> Words -> Characters
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """
        Recursively split the text trying each separator in order until chunks are small enough.
        """
        final_chunks = []
        separator = separators[-1]
        new_separators = []

        # Find the first separator that actually exists in the text
        for i, _s in enumerate(separators):
            if _s == "":
                separator = _s
                break
            if _s in text:
                separator = _s
                new_separators = separators[i + 1 :]
                break

        # Split the text
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Reconstruct the splits with the separator included where appropriate
        good_splits = []
        for s in splits:
            if s:
                good_splits.append(s)

        # Merge splits into chunks of appropriate size
        current_chunk = []
        current_length = 0

        def _merge_current_chunk():
            if current_chunk:
                joined = separator.join(current_chunk)
                if joined.strip():
                    final_chunks.append(joined)
            current_chunk.clear()

        for s in good_splits:
            s_len = len(s)

            # If a single split is STILL too large, we need to recurse on it
            if s_len > self.chunk_size and new_separators:
                # Flush what we have so far
                _merge_current_chunk()
                current_length = 0

                # Recurse on this big split
                recursive_chunks = self._split_text(s, new_separators)
                final_chunks.extend(recursive_chunks)
                continue

            # If adding this split exceeds the chunk size, flush the current chunk
            if current_length + s_len + (len(separator) if current_chunk else 0) > self.chunk_size:
                _merge_current_chunk()
                current_length = 0

            current_chunk.append(s)
            current_length += s_len + (len(separator) if len(current_chunk) > 1 else 0)

        # Flush any remaining text
        _merge_current_chunk()
        return final_chunks

    def _apply_overlap(self, splits: list[str]) -> list[str]:
        """
        Takes the base splits and applies the sliding overlap by looking back
        and prepending text from the previous split up to `chunk_overlap` chars.
        """
        if not self.chunk_overlap or len(splits) <= 1:
            return splits

        overlapped_chunks = [splits[0]]

        for i in range(1, len(splits)):
            current = splits[i]
            previous = splits[i - 1]

            # Grab up to `chunk_overlap` characters from the end of the previous chunk
            # but try to snap to a word boundary (space) if possible so we don't chop words
            overlap_text = previous[-self.chunk_overlap :]
            space_idx = overlap_text.find(" ")

            if space_idx != -1 and space_idx < len(overlap_text) - 1:
                overlap_text = overlap_text[space_idx + 1 :]

            overlapped_chunks.append(f"{overlap_text} {current}".strip())

        return overlapped_chunks

    def chunk(self, document: Document) -> list[Chunk]:
        """
        Implementation of the recursive splitting logic.
        """
        text = document.content
        if not text:
            return []

        # 1. Get the base splits using the recursive strategy
        base_splits = self._split_text(text, self.separators)

        # 2. Apply overlap between the chunks
        final_texts = self._apply_overlap(base_splits)

        # 3. Create Chunk models
        chunks = []
        for idx, chunk_text in enumerate(final_texts):
            if chunk_text.strip():
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document.id,
                        content=chunk_text.strip(),
                        chunk_index=idx,
                        metadata=document.metadata.model_dump(),
                    )
                )

        logger.info(
            f"Recursive chunker created {len(chunks)} chunks",
            extra={"extra_fields": {"strategy": "recursive"}},
        )
        return chunks
