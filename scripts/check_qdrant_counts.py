import asyncio
from qdrant_client import AsyncQdrantClient

async def check_counts():
    client = AsyncQdrantClient(url="http://localhost:6333")
    strategies = ["fixed", "sliding", "structure", "semantic"]
    
    print("Strategy Point Counts:")
    for s in strategies:
        try:
            coll_name = f"deepvault_{s}"
            count = await client.count(coll_name)
            print(f" - {coll_name}: {count.count} points")
        except Exception as e:
            print(f" - {coll_name}: FAILED ({e})")
            
    await client.close()

if __name__ == "__main__":
    asyncio.run(check_counts())
