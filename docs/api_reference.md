# DeepVault API Reference

The DeepVault API is versioned under `/api/v1` and secured via an API Key.

## Authentication

All protected endpoints require the `X-API-KEY` header.
- **Header:** `X-API-KEY: <your_secret_key>`
- **Default Key:** `deepvault_secret_key` (configured in `.env` or `app/config.py`)

## Core Endpoints

### 1. Query (Standard RAG)
`POST /api/v1/query`

Performs a standard RAG search and returns a fully generated JSON response.

**Request Schema:**
```json
{
  "query_text": "What are the chunking strategies?",
  "top_k": 5,
  "chunking_strategy": "sliding",
  "retrieval_strategy": "auto",
  "use_query_rewriting": false
}
```

**Response Schema:**
```json
{
  "answer": "DeepVault supports four chunking strategies...",
  "sources": [
    {
      "chunk_id": "uuid",
      "content": "...",
      "score": 0.89,
      "metadata": {"source": "architecture.md"}
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 50,
    "total_tokens": 200
  },
  "latency_ms": 1205.4,
  "request_id": "req_123abc",
  "low_confidence": false
}
```

### 2. Stream (Streaming RAG)
`POST /api/v1/stream`

Returns an SSE (Server-Sent Events) stream of tokens as the LLM generates them.

**Request Schema:** Same as `/query`.
**Response Format:** text/event-stream

### 3. Ingest Document
`POST /api/v1/ingest`

Upload a file (PDF, TXT, MD) to ingest it into the knowledge base.

**Form Data:**
- `file`: The file to upload
- `chunking_strategy` (optional): `fixed`, `sliding`, `semantic`, or `structure`.

### 4. Feedback
`POST /api/v1/feedback`

Submit user feedback for a generated RAG response to track real-world quality.

**Request Schema:**
```json
{
  "request_id": "req_123abc",
  "query_text": "What are the chunking strategies?",
  "answer_text": "...",
  "rating": 5,
  "comment": "Perfect answer!"
}
```

### 5. Health Checks
`GET /api/v1/health`
Fast liveness probe (checks if API is running and Redis is reachable).

`GET /api/v1/health/detailed`
Deep readiness probe. Checks latency and status of Redis, Qdrant, and the LLM API.

## Error Handling

DeepVault returns standard HTTP status codes:
- `400 Bad Request`: Invalid parameters or unsupported file type.
- `403 Forbidden`: Missing or invalid API key.
- `404 Not Found`: Endpoint or document not found.
- `422 Unprocessable Entity`: Schema validation error (FastAPI standard).
- `429 Too Many Requests`: Rate limit exceeded.
- `500 Internal Server Error`: An unexpected failure occurred.
