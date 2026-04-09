import sys
import random
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

def main():
    print('PULSE TEST: Starting...')
    try:
        client = QdrantClient(url='http://localhost:6333')
        print('PULSE TEST: Connection to Qdrant successful.')
        
        # Generate 5 random points
        points = []
        for i in range(5):
            vector = [random.random() for _ in range(384)]
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={'content': f'Random Test Chunk {i}', 'test': True}
            ))
            
        print('PULSE TEST: Upserting 5 random points...')
        res = client.upsert(collection_name='deepvault_fixed', points=points)
        print(f'PULSE TEST: SUCCESS! Upsert result: {res.status}')
        
    except Exception as e:
        print(f'PULSE TEST: FAILED: {str(e)}')

if __name__ == '__main__':
    main()
