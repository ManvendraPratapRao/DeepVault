# Project Atlas: Core Hybrid Search Migration
## Background
Project Atlas is a critical milestone towards modernizing our search infrastructure. The goal is to migrate the core search functionality from a traditional BM25-based system to a hybrid BM25+vector search approach using Qdrant and Elasticsearch. This will improve search relevancy, scalability, and performance.

## Architecture Diagram/Overview
```
          +---------------+
          |  User Request  |
          +---------------+
                  |
                  | API Gateway (FastAPI)
                  v
+-------------------------------+
|         Search Service          |
+-------------------------------+
|  BM25 Search (Elasticsearch)    |
|  Vector Search (Qdrant)         |
|  Hybrid Search Fusion          |
+-------------------------------+
                  |
                  | Hassan (ML Ops Engineer)
                  |  (Qdrant and ML Model Training)
                  v
+-------------------------------+
|        ML Model Training        |
|  (Qdrant and Elasticsearch)     |
+-------------------------------+
```

## Milestones
- **Week 1-2**: Elasticsearch schema migration and BM25 search setup
- **Week 3-4**: Qdrant installation and ML model training
- **Week 5-6**: Hybrid search fusion development and testing
- **Week 7-8**: Performance optimization and deployment preparation
- **Week 9**: Deployment and monitoring setup

## End Goals
- **Improved search relevancy**: 20% increase in search accuracy
- **Enhanced scalability**: Support up to 50,000 concurrent searches
- **Optimized performance**: 30% reduction in search latency
- **Reduced costs**: Lower Elasticsearch costs through more efficient search queries

## Assumptions and Dependencies
- Hassan will provide ML model training and Qdrant expertise
- FastAPI and Elasticsearch will be used as per existing infrastructure
- Qdrant will be used as the vector search engine