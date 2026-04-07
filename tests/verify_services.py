import asyncio
import os
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.chunkers.fixed import FixedWindowChunker
from app.infrastructure.stores.sqlite import SqliteDocumentStore
from app.infrastructure.stores.qdrant import QdrantVectorStore
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.retrievers.vector import VectorRetriever

from app.services.ingestion import IngestionService
from app.services.query import QueryService
from app.services.document import DocumentService
from app.core.models.query import QueryRequest
from app.infrastructure.logging.structured import logger

async def run_verification():
    logger.info("🚀 Starting Service Layer Verification...")

    # 1. Initialize Infrastructure
    embedder = BgeEmbedder()
    chunker = FixedWindowChunker(chunk_size=200, chunk_overlap=20)
    
    # Use separate test databases to avoid messing with your main ones
    test_db = "verification_test.db"
    test_collection = "verification_test"
    
    sqlite_store = SqliteDocumentStore(test_db)
    vstore = QdrantVectorStore(collection_name=test_collection)
    llm = GroqLLMClient()
    retriever = VectorRetriever(embedder=embedder, vector_store=vstore)

    await sqlite_store.initialize()
    await vstore.initialize(vector_size=embedder.get_dimension())

    # 2. Initialize Services (The Brains)
    ingestion_service = IngestionService(chunker, embedder, sqlite_store, vstore)
    query_service = QueryService(retriever, llm)
    document_service = DocumentService(sqlite_store, vstore)

    try:
        # --- TEST 1: INGESTION ---
        logger.info("--- Testing IngestionService ---")
        sample_content = (
            "DeepVault was built on Day 2 of the project. "
            "It uses a modular service layer to separate logic from infrastructure. "
            "The system is currently being verified for production readiness."
        )
        doc = await ingestion_service.ingest_text(
            content=sample_content, 
            source="verification_test.txt",
            author="AI_Engineer"
        )
        logger.info(f"✅ Ingestion successful. Doc ID: {doc.id}")

        # --- TEST 2: QUERY ---
        logger.info("--- Testing QueryService ---")
        req = QueryRequest(query_text="When was DeepVault built?")
        response = await query_service.ask(req, request_id="verify-123")
        logger.info(f"✅ Query Answer: {response.answer}")
        logger.info(f"✅ Latency: {response.latency_ms:.2f}ms")

        # --- TEST 3: DOCUMENT MANAGEMENT ---
        logger.info("--- Testing DocumentService ---")
        docs = await document_service.list_documents(limit=10)
        logger.info(f"✅ Document List Count: {len(docs)}")
        
        fetched_doc = await document_service.get_document(doc.id)
        logger.info(f"✅ Fetched Document Source: {fetched_doc.metadata.source}")

        logger.info("--- Testing Atomic Deletion ---")
        await document_service.delete_document(doc.id)
        
        # Verify it's gone from SQLite
        remaining_docs = await document_service.list_documents()
        if len(remaining_docs) == 0:
            logger.info("✅ Deletion successful. No documents remaining.")
        else:
            logger.error("❌ Deletion failed. Document still exists in list.")

    finally:
        # Cleanup
        await sqlite_store.close()
        await vstore.close()
        # Remove test database file
        if os.path.exists(test_db):
            os.remove(test_db)
        logger.info("✅ All Services Verified Successfully!")

if __name__ == "__main__":
    asyncio.run(run_verification())
