import asyncio
from app.infrastructure.embedders.bge import BgeEmbedder
import numpy as np
import sys

async def main():
    embedder = BgeEmbedder()
    q = await embedder.embed_text("what is deepvault")
    doc = await embedder.embed_batch(["Performance Requirements, and Open Questions. They also mentioned realistic technical details with specific frameworks, databases, APIs, and metrics. Let me break this down step by step. First, the Overview. I should explain what Project Deepvault is. Since it's a secure data storage solution, maybe it's for enterprise clients. It needs high availability, scalability, and security. Maybe it uses blockchain for tamper resistance. I should mention the use case"])
    
    q_vec = np.array(q)
    doc_vec = np.array(doc[0])
    
    # Cosine similarity
    cos_sim = np.dot(q_vec, doc_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(doc_vec))
    print(f"Cosine Similarity: {cos_sim}")

if __name__ == "__main__":
    asyncio.run(main())
