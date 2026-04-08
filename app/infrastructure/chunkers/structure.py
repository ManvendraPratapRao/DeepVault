import re
import uuid

from app.core.interfaces.chunker import BaseChunker
from app.core.models.document import Chunk, Document
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.logging.structured import logger


class StructureChunker(BaseChunker):
    """
    Splits documents along Markdown heading boundaries (# → ######).
    Each heading starts a new chunk, preserving the document's logical structure.

    Fallback: If no headings are found (e.g., extracted PDF text),
    it delegates entirely to FixedWindowChunker.

    Overflow: If a section exceeds max_section_size, it is sub-chunked
    using FixedWindowChunker internally.
    """

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)

    def __init__(
        self,
        max_section_size: int = 1500,
        fallback_chunk_size: int = 500,
        fallback_overlap: int = 100,
    ):
        self.max_section_size = max_section_size
        self.fallback_chunk_size = fallback_chunk_size
        self.fallback_overlap = fallback_overlap
        # Pre-build the fallback chunker
        self._fallback = FixedWindowChunker(chunk_size=fallback_chunk_size, chunk_overlap=fallback_overlap)

    def _extract_sections(self, text: str) -> list[tuple[str | None, str]]:
        """
        Parse text into (heading, body) pairs.
        Content before the first heading gets heading=None.
        """
        lines = text.split("\n")
        sections: list[tuple[str | None, str]] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if self.HEADING_PATTERN.match(line):
                # Save the previous section
                body = "\n".join(current_lines).strip()
                if body or current_heading:
                    sections.append((current_heading, body))
                current_heading = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Save the final section
        body = "\n".join(current_lines).strip()
        if body or current_heading:
            sections.append((current_heading, body))

        return sections

    def chunk(self, document: Document) -> list[Chunk]:
        """
        1. Extract heading-based sections
        2. If no headings found → fallback to FixedWindowChunker
        3. If a section is too long → sub-chunk it with FixedWindowChunker
        """
        sections = self._extract_sections(document.content)

        # Check if any headings were actually found
        has_headings = any(heading is not None for heading, _ in sections)

        if not has_headings:
            logger.info("No Markdown headings detected — falling back to FixedWindowChunker")
            return self._fallback.chunk(document)

        # Build chunks from structured sections
        chunks: list[Chunk] = []
        chunk_idx = 0

        for heading, body in sections:
            # Combine heading + body into the chunk text
            if heading and body:
                section_text = f"{heading}\n{body}"
            elif heading:
                section_text = heading
            else:
                section_text = body

            if not section_text.strip():
                continue

            # If section is too long, sub-chunk it
            if len(section_text) > self.max_section_size:
                sub_doc = Document(
                    id=document.id,
                    content=section_text,
                    metadata=document.metadata,
                    hash=document.hash,
                )
                sub_chunks = self._fallback.chunk(sub_doc)

                for sc in sub_chunks:
                    sc.document_id = document.id
                    sc.chunk_index = chunk_idx
                    chunks.append(sc)
                    chunk_idx += 1
            else:
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document.id,
                        content=section_text,
                        chunk_index=chunk_idx,
                        metadata=document.metadata.model_dump(),
                    )
                )
                chunk_idx += 1

        logger.info(
            f"Structure chunker created {len(chunks)} chunks from {len(sections)} sections",
            extra={"extra_fields": {"has_headings": has_headings}},
        )
        return chunks
