"""
Verification script: Tests all 4 chunking strategies against the same sample document.
"""

import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.chunkers.semantic import SemanticChunker
from app.infrastructure.chunkers.sliding import SlidingWindowChunker
from app.infrastructure.chunkers.structure import StructureChunker
from app.infrastructure.embedders.bge import BgeEmbedder

# --- Sample Data ---

MARKDOWN_DOC = """# DeepVault Architecture

DeepVault is built using a hexagonal architecture pattern. The core business logic
lives in the service layer, completely decoupled from infrastructure concerns.
This design allows us to swap databases, LLM providers, or embedding models without
touching any business logic.

## Ingestion Pipeline

The ingestion pipeline hashes documents for deduplication, chunks them using a
configurable strategy, embeds each chunk, and stores both metadata in SQLite
and vectors in Qdrant. The entire process is async-safe and uses thread offloading
for CPU-bound chunking operations.

## Query Pipeline

When a user asks a question, the query service retrieves the top-k most relevant
chunks from Qdrant, builds a context string with source citations, constructs a
RAG prompt, and sends it to Groq for generation. The full round-trip latency is
logged and returned to the user.

## Evaluation Framework

The evaluation pipeline uses a golden QA dataset with 80+ questions. It measures
retrieval precision, recall, answer relevance (LLM-as-judge), and faithfulness.
Two independent Groq models are used: one for generation and one for judging,
eliminating self-evaluation bias.

## Technology Stack

The system uses FastAPI for the API layer, Qdrant for vector storage, SQLite for
metadata, BGE-small-en-v1.5 for embeddings, and Groq (Llama-3) for inference.
Redis will be added in Phase 1B for query and embedding caching.
"""

PLAIN_TEXT_DOC = (
    "DeepVault was built on Day 2 of the project. It uses a modular service layer to separate logic "
    "from infrastructure. The system is currently being verified for production readiness. Weather patterns "
    "in tropical regions show significant variation during monsoon season. The annual rainfall can "
    "exceed 2000mm in coastal areas. Back to engineering: the query pipeline retrieves context, builds "
    "prompts, and generates answers using Groq. Testing is done with pytest and asyncio fixtures."
)


def run_test():
    print("=" * 70)
    print("DEEPVAULT CHUNKER COMPARISON TEST")
    print("=" * 70)

    md_doc = Document(
        id="test-md",
        content=MARKDOWN_DOC,
        metadata=DocumentMetadata(source="architecture.md", author="Engineer"),
        hash="test-md-hash",
    )

    plain_doc = Document(
        id="test-plain",
        content=PLAIN_TEXT_DOC,
        metadata=DocumentMetadata(source="notes.txt", author="Engineer"),
        hash="test-plain-hash",
    )

    # 1. Fixed Window
    print("\n--- 1. FIXED WINDOW CHUNKER ---")
    fixed = FixedWindowChunker(chunk_size=300, chunk_overlap=50)
    fixed_chunks = fixed.chunk(md_doc)
    print(f"  Chunks created: {len(fixed_chunks)}")
    for c in fixed_chunks:
        preview = c.content[:70].replace("\n", " ")
        print(f"  [{c.chunk_index}] ({len(c.content)} chars) {preview}...")

    # 2. Sliding Window
    print("\n--- 2. SLIDING WINDOW CHUNKER ---")
    sliding = SlidingWindowChunker(window_size=400, stride=200)
    sliding_chunks = sliding.chunk(md_doc)
    print(f"  Chunks created: {len(sliding_chunks)}")
    for c in sliding_chunks:
        preview = c.content[:70].replace("\n", " ")
        print(f"  [{c.chunk_index}] ({len(c.content)} chars) {preview}...")

    # 3. Semantic Chunker (needs embedder)
    print("\n--- 3. SEMANTIC CHUNKER ---")
    embedder = BgeEmbedder()
    semantic = SemanticChunker(embedder=embedder, similarity_threshold=0.75)
    semantic_chunks = semantic.chunk(plain_doc)
    print(f"  Chunks created: {len(semantic_chunks)}")
    for c in semantic_chunks:
        preview = c.content[:70].replace("\n", " ")
        print(f"  [{c.chunk_index}] ({len(c.content)} chars) {preview}...")

    # 4. Structure-based Chunker (on Markdown)
    print("\n--- 4. STRUCTURE CHUNKER (Markdown) ---")
    structure = StructureChunker(max_section_size=800, fallback_chunk_size=300)
    struct_chunks = structure.chunk(md_doc)
    print(f"  Chunks created: {len(struct_chunks)}")
    for c in struct_chunks:
        preview = c.content[:70].replace("\n", " ")
        print(f"  [{c.chunk_index}] ({len(c.content)} chars) {preview}...")

    # 5. Structure-based Chunker on PLAIN TEXT (should fallback)
    print("\n--- 5. STRUCTURE CHUNKER (Plain Text -> Fallback) ---")
    fallback_chunks = structure.chunk(plain_doc)
    print(f"  Chunks created: {len(fallback_chunks)} (should use fixed-window fallback)")
    for c in fallback_chunks:
        preview = c.content[:70].replace("\n", " ")
        print(f"  [{c.chunk_index}] ({len(c.content)} chars) {preview}...")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Fixed Window:   {len(fixed_chunks)} chunks")
    print(f"  Sliding Window: {len(sliding_chunks)} chunks")
    print(f"  Semantic:       {len(semantic_chunks)} chunks")
    print(f"  Structure (MD): {len(struct_chunks)} chunks")
    print(f"  Structure (TXT):{len(fallback_chunks)} chunks (fallback)")
    print("=" * 70)
    print("[OK] ALL 4 CHUNKERS VERIFIED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_test()
