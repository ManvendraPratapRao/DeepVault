import time

from app.api.middleware.metrics import record_query_metrics
from app.core.exceptions import RetrievalError
from app.core.interfaces.llm_client import BaseLLMClient
from app.core.interfaces.reranker import BaseReranker
from app.core.interfaces.retriever import BaseRetriever
from app.core.interfaces.rewriter import BaseQueryRewriter
from app.core.models.query import QueryRequest, QueryResponse
from app.infrastructure.logging.structured import logger
from app.infrastructure.query.classifier import QueryClassifier
from app.infrastructure.query.decomposer import QueryDecomposer
from app.infrastructure.query.router import QueryRouter
from app.prompts.v1 import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.services.cache_service import CacheService


class QueryService:
    """
    Orchestrator for the RAG query pipeline.
    Coordinates between retrieval and LLM generation.
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        llm_client: BaseLLMClient,
        cache_service: CacheService | None = None,
        reranker: BaseReranker | None = None,
        rewriter: BaseQueryRewriter | None = None,
        router: QueryRouter | None = None,
        decomposer: QueryDecomposer | None = None,
    ):
        self.retriever = retriever
        self.llm_client = llm_client
        self.cache_service = cache_service
        self.reranker = reranker
        self.rewriter = rewriter
        self.router = router
        self.decomposer = decomposer

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

        # 2. Query Rewriting (Session 8)
        # Expansion helps the retriever find results for vague or abbreviated queries
        search_query = request.query_text
        if request.use_query_rewriting and self.rewriter:
            try:
                search_query = await self.rewriter.rewrite(request.query_text)
            except Exception as e:
                logger.error(f"Query rewriting failed: {e}. Falling back to raw query.")

        # 2. Retrieve relevant chunks from the Vector Store
        # We target the strategy-specific collection if requested
        collection_name = f"deepvault_{request.chunking_strategy}" if request.chunking_strategy else None

        # Guard against unimplemented retrieval strategies (unless vector or hybrid)
        valid_strategies = {"vector", "hybrid", "hybrid_rerank", "auto"}
        strat = (request.retrieval_strategy or "vector").lower()
        if strat not in valid_strategies:
            raise NotImplementedError(f"Retrieval strategy '{strat}' is not yet implemented. Known: {valid_strategies}")

        # --- Phase 3: Query Router ---
        # If strategy is 'auto', classify the query and route to best strategy
        query_type: str | None = None
        if strat == "auto" and self.router:
            query_type, strat = self.router.classify_and_route(search_query)
            logger.info(f"Router: type={query_type!r} → strategy={strat!r}")
        elif strat == "auto":
            strat = "hybrid"  # Sensible default when router not wired

        collection_display = collection_name or "Default"
        logger.info(
            f"Strategy: chunking={request.chunking_strategy!r} "
            f"retrieval={strat!r} collection={collection_display!r}",
            extra={
                "extra_fields": {
                    "chunking_strategy": request.chunking_strategy,
                    "retrieval_strategy": strat,
                    "query_type": query_type,
                    "collection": collection_name,
                }
            },
        )

        # If we are reranking, we fetch more candidate chunks initially
        fetch_k = request.top_k * 4 if strat == "hybrid_rerank" else request.top_k

        # --- Phase 3: Query Decomposer ---
        # For 'complex' queries, decompose into sub-queries and retrieve in parallel
        if query_type == "complex" and self.decomposer:
            chunks = await self.decomposer.decompose_and_retrieve(
                query=search_query,
                retriever=self.retriever,
                top_k=fetch_k,
                collection_name=collection_name,
            )
        else:
            chunks = await self.retriever.retrieve(
                query=search_query, top_k=fetch_k, filters=request.filters, collection_name=collection_name
            )

        # 2. Handle empty retrieval (Production Safety)
        if not chunks:
            raise RetrievalError("No relevant documents found for this query.", detail={"query": request.query_text})

        # 3. Optional Reranking Step (Session 7)
        if strat == "hybrid_rerank" and self.reranker:
            logger.info(f"Reranking {len(chunks)} candidate chunks using Cross-Encoder...")
            chunks = await self.reranker.rerank(query=search_query, chunks=chunks, top_k=request.top_k)
            logger.info(f"Reranking complete. Selected top {len(chunks)} semantic matches.")

        # 3. Build the Context String with citations
        # We include the source name and chunk index so the LLM can reference them
        context_blocks = []
        for chunk in chunks:
            source_info = chunk.metadata.get("source", "Unknown Source")
            block = f"[Source: {source_info}, Chunk: {chunk.chunk_index}]\n{chunk.content}"
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)

        # 4. Build the Final Prompt
        # We manually replace {context} and {question} to avoid crashes if papers have braces.
        final_user_prompt = RAG_USER_TEMPLATE.replace("{context}", context_str).replace(
            "{question}", request.query_text
        )

        # 5. Generate the Answer via LLM (Groq)
        # We pass our specialized RAG_SYSTEM_PROMPT to ensure groundedness
        # This now returns a structured LLMResult with telemetry
        llm_result = await self.llm_client.generate(prompt=final_user_prompt, system_prompt=RAG_SYSTEM_PROMPT)

        # 6. Finalize Performance Metrics and Sanitize Metadata
        latency_ms = (time.perf_counter() - start_time) * 1000

        # High-Availability Sanitization: Ensure metadata is JSON serializable
        # Senior Dev Tip: We convert datetime objects and other complex types to strings here
        # to prevent 500 errors during final pydantic validation/serialization.
        for chunk in chunks:
            if hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
                for k, v in chunk.metadata.items():
                    if hasattr(v, "isoformat"):  # Handle datetime objects
                        chunk.metadata[k] = v.isoformat()
                    elif not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                        chunk.metadata[k] = str(v)

        logger.info(
            "Query answered successfully (Cache Miss)",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "num_sources": len(chunks),
                    "cache_miss": True,
                    "prompt_tokens": llm_result.usage.prompt_tokens,
                    "completion_tokens": llm_result.usage.completion_tokens,
                }
            },
        )

        response = QueryResponse(
            answer=llm_result.answer,
            sources=chunks,
            usage=llm_result.usage,
            latency_ms=latency_ms,
            request_id=request_id,
        )

        # Record Prometheus metrics for this query
        record_query_metrics(
            retrieval_strategy=strat,
            chunking_strategy=request.chunking_strategy or "fixed",
            duration_seconds=latency_ms / 1000,
            status="success",
            prompt_tokens=llm_result.usage.prompt_tokens,
            completion_tokens=llm_result.usage.completion_tokens,
        )

        # 7. Cache the semantic result to radically speed up identical future questions
        if self.cache_service:
            await self.cache_service.cache_response(request.query_text, response)

        return response

    async def ask_stream(
        self,
        request: QueryRequest,
        request_id: str = "internal",
    ):
        """
        Streaming variant of the RAG pipeline.

        Runs the full pipeline up to prompt construction, then yields tokens
        from the LLM stream one-by-one.  Returns an async generator of strings.

        Cache note: streaming responses bypass the query cache on egress.
        After the stream completes, the full response is cached in a fire-and-
        forget background task so future identical queries are served instantly.
        """
        import asyncio

        from app.core.models.query import TokenUsage

        start_time = time.perf_counter()

        # --- 1. Cache check (same as ask()) ---
        if self.cache_service:
            cached = await self.cache_service.get_cached_response(request.query_text)
            if cached:
                # Replay from cache token-by-token so the UI still looks "live"
                for word in cached.answer.split(" "):
                    yield word + " "
                return

        # --- 2. Query Rewriting ---
        search_query = request.query_text
        if request.use_query_rewriting and self.rewriter:
            try:
                search_query = await self.rewriter.rewrite(request.query_text)
            except Exception as e:
                logger.error(f"Query rewriting failed in stream: {e}")

        # --- 3. Retrieve ---
        collection_name = f"deepvault_{request.chunking_strategy}" if request.chunking_strategy else None
        strat = (request.retrieval_strategy or "vector").lower()
        fetch_k = request.top_k * 4 if strat == "hybrid_rerank" else request.top_k

        chunks = await self.retriever.retrieve(
            query=search_query,
            top_k=fetch_k,
            filters=request.filters,
            collection_name=collection_name,
        )

        if not chunks:
            yield "[ERROR] No relevant documents found for this query."
            return

        # --- 4. Optional Reranking ---
        if strat == "hybrid_rerank" and self.reranker:
            chunks = await self.reranker.rerank(query=search_query, chunks=chunks, top_k=request.top_k)

        # --- 5. Build Prompt ---
        context_blocks = []
        for chunk in chunks:
            source_info = chunk.metadata.get("source", "Unknown Source")
            block = f"[Source: {source_info}, Chunk: {chunk.chunk_index}]\n{chunk.content}"
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)
        final_user_prompt = RAG_USER_TEMPLATE.replace("{context}", context_str).replace(
            "{question}", request.query_text
        )

        # --- 6. Stream tokens from LLM ---
        accumulated = ""
        async for token in self.llm_client.stream(
            prompt=final_user_prompt, system_prompt=RAG_SYSTEM_PROMPT
        ):
            accumulated += token
            yield token

        # --- 7. Fire-and-forget: cache the full response after stream ends ---
        if self.cache_service and accumulated:
            latency_ms = (time.perf_counter() - start_time) * 1000
            full_response = QueryResponse(
                answer=accumulated,
                sources=chunks,
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                latency_ms=latency_ms,
                request_id=request_id,
            )
            asyncio.create_task(self.cache_service.cache_response(request.query_text, full_response))

