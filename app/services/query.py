import asyncio
import json
import time

from opentelemetry import trace

tracer = trace.get_tracer(__name__)


from app.config import settings
from app.core.exceptions import DeepVaultError, RetrievalError
from app.core.interfaces.llm_client import BaseLLMClient
from app.core.interfaces.reranker import BaseReranker
from app.core.interfaces.retriever import BaseRetriever
from app.core.interfaces.rewriter import BaseQueryRewriter
from app.core.models.query import QueryRequest, QueryResponse, TokenUsage
from app.infrastructure.llm.router import LLMRouter
from app.infrastructure.logging.structured import logger
from app.infrastructure.query.decomposer import QueryDecomposer
from app.infrastructure.query.router import QueryRouter
from app.prompts.v1 import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.services.ab_testing import ABTestingService, get_variant_value
from app.services.cache_service import CacheService


class LowConfidenceError(DeepVaultError):
    """Raised when the top retrieved chunk is below the confidence threshold."""
    def __init__(self, chunks):
        super().__init__("Low context confidence")
        self.chunks = chunks


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
        llm_router: LLMRouter | None = None,
        ab_testing_service: ABTestingService | None = None,
    ):
        self.retriever = retriever
        self.llm_client = llm_client
        self.cache_service = cache_service
        self.reranker = reranker
        self.rewriter = rewriter
        self.router = router
        self.decomposer = decomposer
        self.llm_router = llm_router
        self.ab_testing_service = ab_testing_service

    async def _prepare_rag_context(self, request: QueryRequest, request_id: str) -> tuple[list, str, str | None, str | None, str]:
        """
        Runs the pre-generation RAG pipeline.
        Returns: (chunks, context_str, query_type, model_name, final_user_prompt)
        Raises: RetrievalError, LowConfidenceError
        """
        # --- 1. Query Rewriting ---
        search_query = request.query_text
        if request.use_query_rewriting and self.rewriter:
            with tracer.start_as_current_span("deepvault.query.rewrite") as span:
                try:
                    search_query = await self.rewriter.rewrite(request.query_text)
                    span.set_attribute("query.rewritten", search_query)
                except Exception as e:
                    logger.error(f"Query rewriting failed: {e}. Falling back to raw query.")
                    span.record_exception(e)

        # --- 2. Query Router ---
        collection_name = f"deepvault_{request.chunking_strategy}" if request.chunking_strategy else None
        valid_strategies = {"vector", "hybrid", "hybrid_rerank", "auto"}
        strat = (request.retrieval_strategy or "vector").lower()
        base_strat = strat.replace("_rewrite", "")
        if base_strat not in valid_strategies:
            raise NotImplementedError(f"Retrieval strategy '{strat}' is not yet implemented.")

        query_type: str | None = None
        if strat == "auto" and self.router:
            with tracer.start_as_current_span("deepvault.query.route") as span:
                query_type, strat = self.router.classify_and_route(search_query)
                span.set_attribute("router.query_type", query_type)
                span.set_attribute("router.strategy", strat)
                logger.info(f"Router: type={query_type!r} → strategy={strat!r}")
        elif strat == "auto":
            strat = "hybrid"

        collection_display = collection_name or "Default"
        logger.info(
            f"Strategy: chunking={request.chunking_strategy!r} retrieval={strat!r} collection={collection_display!r}",
            extra={"extra_fields": {"chunking_strategy": request.chunking_strategy, "retrieval_strategy": strat, "query_type": query_type, "collection": collection_name}},
        )

        fetch_k = request.top_k * 2 if "rerank" in strat else request.top_k

        # --- 3. Retrieval & Decomposition ---
        with tracer.start_as_current_span("deepvault.query.retrieve") as span:
            span.set_attribute("retrieval.strategy", strat)
            span.set_attribute("retrieval.fetch_k", fetch_k)
            span.set_attribute("retrieval.collection", collection_display)
            if query_type == "complex" and self.decomposer:
                span.set_attribute("retrieval.decomposed", True)
                chunks = await self.decomposer.decompose_and_retrieve(
                    query=search_query, retriever=self.retriever, top_k=fetch_k, collection_name=collection_name
                )
            else:
                span.set_attribute("retrieval.decomposed", False)
                chunks = await self.retriever.retrieve(
                    query=search_query, top_k=fetch_k, filters=request.filters, collection_name=collection_name
                )
            span.set_attribute("retrieval.num_chunks", len(chunks))

        if not chunks:
            raise RetrievalError("No relevant documents found for this query.", detail={"query": request.query_text})

        # --- 4. Reranking ---
        if strat == "hybrid_rerank" and self.reranker:
            with tracer.start_as_current_span("deepvault.query.rerank") as span:
                span.set_attribute("rerank.initial_chunks", len(chunks))
                logger.info(f"Reranking {len(chunks)} candidate chunks using Cross-Encoder...")
                chunks = await self.reranker.rerank(query=search_query, chunks=chunks, top_k=request.top_k)
                span.set_attribute("rerank.final_chunks", len(chunks))

        # --- 5. Context Confidence Guard ---
        top_score = chunks[0].score or 0.0
        if top_score < settings.CONTEXT_CONFIDENCE_THRESHOLD:
            logger.warning(
                "Low context confidence \u2014 refusing to generate to prevent hallucination.",
                extra={"extra_fields": {"request_id": request_id, "top_chunk_score": top_score, "threshold": settings.CONTEXT_CONFIDENCE_THRESHOLD}},
            )
            raise LowConfidenceError(chunks)

        # --- 6. Build Prompt ---
        context_blocks = []
        for chunk in chunks:
            source_info = chunk.metadata.get("source", "Unknown Source")
            block = f"[Source: {source_info}, Chunk: {chunk.chunk_index}]\n{chunk.content}"
            context_blocks.append(block)

        context_str = "\n\n---\n\n".join(context_blocks)
        final_user_prompt = RAG_USER_TEMPLATE.replace("{context}", context_str).replace("{question}", request.query_text)

        # --- 7. Select LLM Model using LLMRouter ---
        model_name = request.model_name
        if self.llm_router and not model_name:
            model_selection = self.llm_router.select(
                query_type=query_type, query_text=request.query_text, context=context_str
            )
            model_name = model_selection.model_name

        # High-Availability Sanitization for metadata
        for chunk in chunks:
            if hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
                for k, v in chunk.metadata.items():
                    if hasattr(v, "isoformat"):
                        chunk.metadata[k] = v.isoformat()
                    elif not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                        chunk.metadata[k] = str(v)

        return chunks, context_str, query_type, model_name, final_user_prompt

    async def ask(self, request: QueryRequest, request_id: str = "internal") -> QueryResponse:
        start_time = time.perf_counter()
        logger.info(f"Processing query: {request.query_text[:50]}...", extra={"extra_fields": {"request_id": request_id}})
        
        system_prompt = RAG_SYSTEM_PROMPT
        if self.ab_testing_service and request.session_id:
            # 1. Retrieval Strategy A/B Test
            retrieval_variant = get_variant_value(request.session_id, "rerank_vs_hybrid")
            if retrieval_variant:
                request.retrieval_strategy = retrieval_variant
                
            # 2. Prompt Variant A/B Test
            prompt_variant = get_variant_value(request.session_id, "prompt_v3_test")
            if prompt_variant == "v3":
                from app.prompts.v3.system import RAG_SYSTEM_PROMPT as V3_PROMPT
                system_prompt = V3_PROMPT

        if self.cache_service and not request.messages:
            with tracer.start_as_current_span("deepvault.query.cache_check") as span:
                span.set_attribute("query.text", request.query_text)
                cached_resp = await self.cache_service.get_cached_response(request.query_text)
                if cached_resp:
                    span.set_attribute("cache.hit", True)
                    cached_resp.request_id = request_id
                    cached_resp.latency_ms = (time.perf_counter() - start_time) * 1000
                    return cached_resp
                span.set_attribute("cache.hit", False)

        try:
            chunks, context_str, query_type, model_name, final_user_prompt = await self._prepare_rag_context(request, request_id)
        except LowConfidenceError as e:
            return QueryResponse(
                answer="I don't have sufficient information in the knowledge base to answer this question accurately. The retrieved context does not appear to be directly relevant to your query. Please try rephrasing your question or verify that the relevant documents have been ingested.",
                sources=e.chunks, usage=TokenUsage(), latency_ms=(time.perf_counter() - start_time) * 1000, request_id=request_id, low_confidence=True
            )

        with tracer.start_as_current_span("deepvault.query.generate") as span:
            span.set_attribute("generate.model", model_name or "default")
            span.set_attribute("generate.prompt_length", len(final_user_prompt))
            llm_result = await self.llm_client.generate(prompt=final_user_prompt, system_prompt=system_prompt, model_name=model_name, history=request.messages)
            span.set_attribute("generate.answer_length", len(llm_result.answer))
            span.set_attribute("generate.prompt_tokens", llm_result.usage.prompt_tokens)
            span.set_attribute("generate.completion_tokens", llm_result.usage.completion_tokens)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info("Query answered successfully (Cache Miss)", extra={"extra_fields": {"request_id": request_id, "latency_ms": latency_ms, "num_sources": len(chunks), "cache_miss": True}})

        response = QueryResponse(answer=llm_result.answer, sources=chunks, usage=llm_result.usage, latency_ms=latency_ms, request_id=request_id)

        if self.cache_service and not request.messages:
            with tracer.start_as_current_span("deepvault.query.cache_write"):
                await self.cache_service.cache_response(request.query_text, response)
                
        if self.ab_testing_service and request.session_id:
            # Record latency for the prompt test variant
            prompt_variant = get_variant_value(request.session_id, "prompt_v3_test")
            if prompt_variant:
                asyncio.create_task(self.ab_testing_service.record_result(
                    "prompt_v3_test", prompt_variant, "latency", latency_ms, request.session_id
                ))
            
            # Record latency for the retrieval test variant
            retrieval_variant = get_variant_value(request.session_id, "rerank_vs_hybrid")
            if retrieval_variant:
                asyncio.create_task(self.ab_testing_service.record_result(
                    "rerank_vs_hybrid", retrieval_variant, "latency", latency_ms, request.session_id
                ))

        return response

    async def ask_stream(self, request: QueryRequest, request_id: str = "internal"):
        start_time = time.perf_counter()
        
        system_prompt = RAG_SYSTEM_PROMPT
        if self.ab_testing_service and request.session_id:
            retrieval_variant = get_variant_value(request.session_id, "rerank_vs_hybrid")
            if retrieval_variant:
                request.retrieval_strategy = retrieval_variant
                
            prompt_variant = get_variant_value(request.session_id, "prompt_v3_test")
            if prompt_variant == "v3":
                from app.prompts.v3.system import RAG_SYSTEM_PROMPT as V3_PROMPT
                system_prompt = V3_PROMPT

        if self.cache_service and not request.messages:
            cached = await self.cache_service.get_cached_response(request.query_text)
            if cached:
                for word in cached.answer.split(" "):
                    yield word + " "
                return

        try:
            chunks, context_str, query_type, model_name, final_user_prompt = await self._prepare_rag_context(request, request_id)
        except LowConfidenceError:
            yield "⚠️ Insufficient context — the retrieved documents do not appear relevant to your question. Please rephrase or check that the relevant documents have been ingested."
            return
        except RetrievalError:
            yield "[ERROR] No relevant documents found for this query."
            return

        sources_payload = [{"source": c.metadata.get("source", "Unknown"), "content": c.content, "score": c.score} for c in chunks]
        yield f"[SOURCES] {json.dumps(sources_payload)}\n"

        accumulated = ""
        async for token in self.llm_client.stream(prompt=final_user_prompt, system_prompt=system_prompt, model_name=model_name, history=request.messages):
            accumulated += token
            yield token

        if accumulated and not request.messages:
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Cache the response
            if self.cache_service:
                full_response = QueryResponse(answer=accumulated, sources=chunks, usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0), latency_ms=latency_ms, request_id=request_id)
                asyncio.create_task(self.cache_service.cache_response(request.query_text, full_response))
            
            # Record A/B Testing latency
            if self.ab_testing_service and request.session_id:
                prompt_variant = get_variant_value(request.session_id, "prompt_v3_test")
                if prompt_variant:
                    asyncio.create_task(self.ab_testing_service.record_result(
                        "prompt_v3_test", prompt_variant, "latency", latency_ms, request.session_id
                    ))
                retrieval_variant = get_variant_value(request.session_id, "rerank_vs_hybrid")
                if retrieval_variant:
                    asyncio.create_task(self.ab_testing_service.record_result(
                        "rerank_vs_hybrid", retrieval_variant, "latency", latency_ms, request.session_id
                    ))
