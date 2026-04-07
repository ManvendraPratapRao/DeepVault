import asyncio
import uuid
import hashlib
from app.infrastructure.logging.structured import logger
from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.stores.sqlite import SqliteDocumentStore
from app.infrastructure.stores.qdrant import QdrantVectorStore
from app.infrastructure.retrievers.vector import VectorRetriever
from app.infrastructure.llm.groq import GroqLLMClient

async def run_smoke_test():
    logger.info("🚀 Starting DeepVault Infrastructure Smoke Test...")

    # 1. Initialize Components
    embedder = BgeEmbedder()
    sqlite_store = SqliteDocumentStore("test_deepvault.db")
    vstore = QdrantVectorStore(collection_name="test_collection")
    llm = GroqLLMClient()
    
    # Initialize Databases
    await sqlite_store.initialize()
    await vstore.initialize(vector_size=embedder.get_dimension())

    # 2. Prepare Sample Data
    content = (
        "Project DeepVault is an autonomous RAG system. "
        "It uses Groq for inference and Qdrant for vector storage. "
        "The system is designed for high-performance enterprise search."
    )
    doc_hash = hashlib.sha256(content.encode()).hexdigest()
    doc = Document(
        content=content,
        hash=doc_hash,
        metadata=DocumentMetadata(source="smoke_test_manual")
    )

    # 3. Test Chunking
    logger.info("Testing Chunker...")
    chunker = FixedWindowChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk(doc)
    logger.info(f"Generated {len(chunks)} chunks.")

    # 4. Test Embedding
    logger.info("Testing Embedder...")
    # Embed the chunks
    contents = [c.content for c in chunks]
    embeddings = await embedder.embed_batch(contents)
    for i, chunk in enumerate(chunks):
        chunk.embedding = embeddings[i]
    logger.info("Embeddings generated successfully.")

    # 5. Test Storage (SQL + Vector)
    logger.info("Testing Storage...")
    await sqlite_store.upsert_document(doc)
    await vstore.upsert_chunks(chunks)
    logger.info("Data persisted to SQLite and Qdrant.")

    # 6. Test Retrieval
    logger.info("Testing Retriever...")
    retriever = VectorRetriever(embedder=embedder, vector_store=vstore)
    query = "How does DeepVault handle inference?"
    retrieved_chunks = await retriever.retrieve(query, top_k=2)
    
    if not retrieved_chunks:
        raise ValueError("Retrieval failed: No chunks found.")
    logger.info(f"Retrieved {len(retrieved_chunks)} relevant chunks.")

    # 7. Test LLM Generation (The Final RAG Loop)
    logger.info("Testing LLM Generation...")
    context = "\n".join([c.content for c in retrieved_chunks])
    rag_prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer based purely on the context:"
    
    answer = await llm.generate(rag_prompt)
    logger.info("--- FINAL RAG RESPONSE ---")
    logger.info(answer)
    logger.info("✅ Smoke Test Passed Successfully!")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
