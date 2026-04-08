import time

from app.core.exceptions import RetrievalError
from app.core.interfaces.llm_client import BaseLLMClient
from app.core.interfaces.retriever import BaseRetriever
from app.core.models.query import QueryRequest, QueryResponse
from app.infrastructure.logging.structured import logger
from app.prompts.v1 import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.services.cache_service import CacheService


class QueryService:
    """
    Orchestrator for the RAG query pipeline.
    Coordinates between retrieval and LLM generation.
    """

    def __init__(self, retriever: BaseRetriever, llm_client: BaseLLMClient, cache_service: CacheService | None = None):
        self.retriever = retriever
        self.llm_client = llm_client
        self.cache_service = cache_service

    async def ask(self, request: QueryRequest, request_id: str = "internal") -> QueryResponse:
        """
        The core RAG loop: Retrieve -> Prompt -> Generate.
        """
        start_time = time.perf_counter()

        logger.info(
            f"Processing query: {request.query_text[:50]}...",
            extra={"extra_fields": {"request_id": request_id}},
        )

        # 1. Check Redis Cache for instantaneous semantic hits!
        if self.cache_service:
            cached_resp = await self.cache_service.get_cached_response(request.query_text)
            if cached_resp:
                # We overwrite the cached request_id with the live transaction IDs to keep traces clean
                cached_resp.request_id = request_id
                cached_resp.latency_ms = (time.perf_counter() - start_time) * 1000
                return cached_resp

        # 2. Retrieve relevant chunks from the Vector Store
        # We use top_k=5 as the default for high-quality context
        chunks = await self.retriever.retrieve(query=request.query_text, top_k=5, filters=request.filters)

        # 2. Handle empty retrieval (Production Safety)
        if not chunks:
            raise RetrievalError("No relevant documents found for this query.", detail={"query": request.query_text})

        # 3. Build the Context String with citations
        # We include the source name and chunk index so the LLM can reference them
        context_blocks = []
        for chunk in chunks:
            source_info = chunk.metadata.get("source", "Unknown Source")
            block = f"[Source: {source_info}, Chunk: {chunk.chunk_index}]\n{chunk.content}"
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)

        # 4. Build the Final Prompt
        # RAG_USER_TEMPLATE expects {context} and {question}
        final_user_prompt = RAG_USER_TEMPLATE.format(context=context_str, question=request.query_text)

        # 5. Generate the Answer via LLM (Groq)
        # We pass our specialized RAG_SYSTEM_PROMPT to ensure groundedness
        answer = await self.llm_client.generate(prompt=final_user_prompt, system_prompt=RAG_SYSTEM_PROMPT)

        # 6. Finalize Performance Metrics
        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Query answered successfully (Cache Miss)",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "num_sources": len(chunks),
                    "cache_miss": True,
                }
            },
        )

        response = QueryResponse(answer=answer, sources=chunks, latency_ms=latency_ms, request_id=request_id)
        
        # 7. Cache the semantic result to radically speed up identical future questions
        if self.cache_service:
            await self.cache_service.cache_response(request.query_text, response)
            
        return response
