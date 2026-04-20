import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.core.models.query import QueryRequest
from app.dependencies import get_query_service
from app.infrastructure.logging.structured import logger

async def reproduce():
    # The breaking query found in logs
    query = "What would be the correct endpoint and authentication flow to use when updating a model's name and description, assuming I have a valid JWT token for the current session?"
    
    print(f"\n--- REPRODUCTION ATTEMPT ---")
    print(f"Query: {query}")
    
    # We need to initialize the app context dependencies
    from app.dependencies import get_embedder, get_llm_client, get_cache_service, get_reranker, get_query_rewriter
    from app.infrastructure.stores.qdrant import QdrantVectorStore
    
    cache = await get_cache_service()
    embedder = await get_embedder()
    llm = await get_llm_client()
    rewriter = await get_query_rewriter()
    reranker = await get_reranker()
    
    # Target the semantic collection specifically as it's the one panicking
    vector_store = QdrantVectorStore(collection_name="deepvault_semantic")
    
    # Construct the request
    req = QueryRequest(
        query_text=query,
        use_query_rewriting=True,
        chunking_strategy="semantic",
        retrieval_strategy="hybrid_rerank",
        top_k=20
    )
    
    # Directly test the search part
    print(f"Testing Rewriter...")
    expanded = await rewriter.rewrite(query)
    print(f"Expanded: {expanded}")
    
    print(f"Testing Embedding...")
    vec = await embedder.embed_text(expanded)
    print(f"Vector size: {len(vec)}")
    
    from qdrant_client.models import NearestQuery
    print(f"Testing Qdrant Search (The suspected crash point)...")
    try:
        # Using explicit NearestQuery to see if it bypasses the internal panic
        results = await vector_store.client.query_points(
            collection_name="deepvault_semantic",
            query=NearestQuery(nearest=query_vector), # Wait, it's 'nearest' in some versions
            limit=80
        )
        print(f"SUCCESS! Found {len(results)} results.")
    except Exception as e:
        # Retry with different parameter name if needed
        try:
           results = await vector_store.client.query_points(
                collection_name="deepvault_semantic",
                query=query_vector, # Fallback to original
                limit=80
            )
           print(f"SUCCESS on Fallback! Found {len(results)} results.")
        except Exception as e2:
           print(f"CRASH DETECTED: {e2}")

if __name__ == "__main__":
    asyncio.run(reproduce())
