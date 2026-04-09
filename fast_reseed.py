import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
import glob
import os

def main():
    print('EMERGENCY SEEDER STARTING...')
    try:
        model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        print('MODEL LOADED SUCCESSFULY (DIM: 384)')
    except Exception as e:
        print(f'CRITICAL: Model load failed: {str(e)}')
        return

    client = QdrantClient(url='http://localhost:6333')
    strategies = ['fixed', 'sliding', 'structure', 'semantic']
    
    # Target file
    logistics_file = 'synthetic_data_v2/logistics/protocol_logistics_v1.md'
    if not os.path.exists(logistics_file):
        print(f'ERROR: File not found: {logistics_file}')
        return
        
    with open(logistics_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Very simple fixed chunker for the alpha test
    chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
    print(f'Created {len(chunks)} test chunks from {logistics_file}')
    
    for strategy in strategies:
        coll = f'deepvault_{strategy}'
        print(f'Initializing collection: {coll}')
        client.recreate_collection(
            collection_name=coll,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        points = []
        for i, text in enumerate(chunks):
            # No prefix for document vectors
            vector = model.encode(text).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={'content': text, 'document_id': 'logistics_test', 'chunk_index': i}
            ))
            
        client.upsert(collection_name=coll, points=points)
        print(f'SUCCESS: Populated {coll} with {len(points)} points.')

if __name__ == '__main__':
    main()
