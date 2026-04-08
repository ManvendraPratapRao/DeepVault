# DeepVault Architecture 🏗️

DeepVault relies entirely on deeply separated Domain-Driven Design architectures naturally utilizing the **Hexagonal (Ports and Adapters)** architectural pattern dynamically.

## Component Flow Structure

```mermaid
graph TD;
    API[FastAPI Endpoints] --> DS[Document Service]
    API --> IS[Ingestion Service]
    API --> QS[Query Service]
    
    IS -.-> CH[Chunker Interface]
    IS -.-> EM[Embedder Interface]
    IS -.-> VD[Vector Store Interface]
    IS -.-> MD[Document Store Interface]

    QS -.-> RT[Retriever Interface]
    QS -.-> LLM[LLM Client Interface]
    QS -.-> CS[Cache Service]

    CS --> R((Redis))
    VD --> Q((Qdrant Db))
    MD --> SQL((SQLite Db))
    LLM --> G((Groq Network))
    EM --> Torch((BAAI/Torch Local))
```

## System Responsibilities

1. **`app.api` (Ports)**: Controls global networking protocols natively (REST mapping, error serialization dynamically natively scaling payloads). 
2. **`app.services` (Business Logic Orchestrators)**: Controls the strict orchestration of external modules dynamically to assemble functional value configurations seamlessly utilizing data sequences natively perfectly abstracted. 
3. **`app.core` (Core Domain Interfaces)**: Configures and bounds strict generic classes explicitly providing computational interfaces mechanically isolating external data types logically.
4. **`app.infrastructure` (Adapters)**: Explicit network arrays mapping strict implementations mathematically matching core abstractions externally against the internet or localized disks natively.
