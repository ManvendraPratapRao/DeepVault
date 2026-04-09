import random
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

def main():
    print('PULSE START')
    try:
        client = QdrantClient(url='http://localhost:6333')
        points = [PointStruct(id=str(uuid.uuid4()), vector=[random.random() for _ in range(384)], payload={'test': True}) for _ in range(5)]
        client.upsert(collection_name='deepvault_fixed', points=points)
        print('PULSE SUCCESS')
    except Exception as e:
        print(f'PULSE ERROR: {str(e)}')

if __name__ == '__main__':
    main()
