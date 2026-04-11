import asyncio
import numpy as np
import json
from pathlib import Path
import fitz
from typing import List, Dict

from app.core.models.document import Document, DocumentMetadata
from app.infrastructure.chunkers.sliding import SlidingWindowChunker
from app.infrastructure.embedders.bge import BgeEmbedder
from app.infrastructure.logging.structured import logger

# Configuration
TEST_PDF = Path("data/curated_papers/Sentence-BERT Sentence Embeddings using Siamese BERT-Networks.pdf")

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class ChunkDiagnostic:
    def __init__(self):
        self.chunker = SlidingWindowChunker(window_size=600, stride=480)
        self.embedder = BgeEmbedder()

    async def run_diagnostics(self, pdf_path: Path):
        logger.info(f"Running Diagnostics on: {pdf_path.name}")
        
        # 1. Extract Full Text
        content = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                content += page.get_text()
        
        doc_obj = Document(
            content=content,
            metadata=DocumentMetadata(source=pdf_path.name),
            hash="diag-hash"
        )
        
        # 2. Chunking
        chunks = self.chunker.chunk(doc_obj)
        logger.info(f"Created {len(chunks)} chunks.")
        
        # 3. Embedding
        chunk_texts = [c.content for c in chunks]
        embeddings = await self.embedder.embed_batch(chunk_texts)
        
        # 4. Continuity Analysis
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = cosine_similarity(embeddings[i], embeddings[i+1])
            similarities.append(sim)
        
        avg_sim = np.mean(similarities) if similarities else 0
        min_sim = np.min(similarities) if similarities else 0
        max_sim = np.max(similarities) if similarities else 0
        
        # 5. Entity Integrity (Simple check for common abbreviations or names cut off)
        # We look for lines ending in lowercase or hanging punctuation
        fragmented_chunks = 0
        for chunk in chunks:
            ends_with_period = chunk.content.strip().endswith(('.', '!', '?'))
            if not ends_with_period:
                fragmented_chunks += 1

        # Report
        report = {
            "filename": pdf_path.name,
            "total_chunks": len(chunks),
            "avg_semantic_continuity": float(avg_sim),
            "min_semantic_continuity": float(min_sim),
            "max_semantic_continuity": float(max_sim),
            "fragmented_chunks_ratio": fragmented_chunks / len(chunks) if chunks else 0
        }
        
        print("\n" + "="*50)
        print(f"DIAGNOSTIC REPORT: {pdf_path.name}")
        print("="*50)
        print(f"Total Chunks:            {report['total_chunks']}")
        print(f"Avg Continuity (Sim):    {report['avg_semantic_continuity']:.4f}")
        print(f"Min Continuity (Sim):    {report['min_semantic_continuity']:.4f} (Lower = risky boundary)")
        print(f"Max Continuity (Sim):    {report['max_semantic_continuity']:.4f} (Higher = redundant overlap)")
        print(f"Fragmented Chunk Ratio:  {report['fragmented_chunks_ratio']:.2%} (Non-sentence endings)")
        print("="*50)
        
        if min_sim < 0.4:
            print("WARNING: Some chunks have very low semantic continuity. Context might be broken.")
        if avg_sim > 0.9:
            print("TIP: Average continuity is very high. You might be able to increase stride to save tokens.")
            
        return report

async def main():
    diagnostic = ChunkDiagnostic()
    papers = list(Path("data/curated_papers").glob("*.pdf"))
    
    if not papers:
        logger.error("No PDFs found in data/curated_papers")
        return

    reports = []
    for paper in papers:
        try:
            report = await diagnostic.run_diagnostics(paper)
            reports.append(report)
        except Exception as e:
            logger.error(f"Failed to diagnose {paper.name}: {e}")

    # Aggregate Report
    avg_continuity = np.mean([r['avg_semantic_continuity'] for r in reports])
    avg_fragmented = np.mean([r['fragmented_chunks_ratio'] for r in reports])
    total_chunks = sum([r['total_chunks'] for r in reports])

    print("\n" + "!"*50)
    print("AGGREGATE RESEARCH PAPER DIAGNOSTICS")
    print("!"*50)
    print(f"Total Papers Processed:  {len(reports)}")
    print(f"Total Chunks Analyzed:   {total_chunks}")
    print(f"Global Avg Continuity:   {avg_continuity:.4f}")
    print(f"Global Avg Fragmentation:{avg_fragmented:.2%}")
    print("!"*50)

if __name__ == "__main__":
    asyncio.run(main())
