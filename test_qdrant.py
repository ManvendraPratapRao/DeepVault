import asyncio
from app.infrastructure.stores.qdrant import QdrantVectorStore
from app.infrastructure.embedders.bge import BgeEmbedder

async def main():
    embedder = BgeEmbedder()
    store = QdrantVectorStore(collection_name="deepvault_recursive")
    
    q_vec = await embedder.embed_text("what is deepvault")
    
    results = await store.search(q_vec, top_k=3)
    for r in results:
        print(f"Score: {r.score} | Content: {r.content[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
