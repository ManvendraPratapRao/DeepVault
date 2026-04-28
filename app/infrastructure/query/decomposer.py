"""
Query Decomposer — breaks complex multi-part queries into focused sub-queries
that can each be retrieved independently, then merges the results.

Design:
    - Only activated for 'complex' query type (as determined by QueryClassifier).
    - Sub-queries are executed in parallel via asyncio.gather() for speed.
    - Results are deduplicated by chunk ID before being returned.
    - Falls back to the original query on LLM failure (fail-open design).

Why decompose?
    Complex queries like "What are the trade-offs of hybrid retrieval and
    when should I use reranking?" have two distinct information needs.
    A single retrieval pass often retrieves chunks relevant to one part
    but not the other. Decomposing into two focused sub-queries doubles
    the chance of retrieving grounding context for each aspect.
"""

import asyncio

from app.core.interfaces.llm_client import BaseLLMClient
from app.core.interfaces.retriever import BaseRetriever
from app.core.models.document import Chunk
from app.infrastructure.logging.structured import logger
from app.prompts.v3.decomposition import (
    DECOMPOSITION_SYSTEM_PROMPT,
    DECOMPOSITION_USER_TEMPLATE,
)

_MAX_SUB_QUERIES = 4
_MIN_SUB_QUERY_LENGTH = 8  # Characters — ignore empty / noise lines


class QueryDecomposer:
    """
    LLM-based query decomposer for complex multi-part questions.

    Typical usage (in QueryService):
        if query_type == "complex":
            chunks = await decomposer.decompose_and_retrieve(query, retriever, top_k)
        else:
            chunks = await retriever.retrieve(query, top_k)
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def decompose(self, query: str) -> list[str]:
        """
        Calls the LLM to decompose a complex query into sub-queries.

        Returns:
            A list of 1–4 sub-query strings. Returns [query] on failure.
        """
        prompt = DECOMPOSITION_USER_TEMPLATE.replace("{query}", query)

        try:
            result = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=DECOMPOSITION_SYSTEM_PROMPT,
            )

            raw = result.answer.strip()
            lines = [ln.strip() for ln in raw.splitlines() if len(ln.strip()) >= _MIN_SUB_QUERY_LENGTH]

            if not lines:
                logger.warning("Decomposer returned no valid sub-queries. Using original query.")
                return [query]

            sub_queries = lines[:_MAX_SUB_QUERIES]
            logger.info(
                f"Query decomposed into {len(sub_queries)} sub-queries",
                extra={"extra_fields": {"original": query[:80], "sub_queries": sub_queries}},
            )
            return sub_queries

        except Exception as e:
            logger.error(f"Query decomposition failed: {e}. Falling back to original query.")
            return [query]

    async def decompose_and_retrieve(
        self,
        query: str,
        retriever: BaseRetriever,
        top_k: int,
        collection_name: str | None = None,
    ) -> list[Chunk]:
        """
        Decomposes the query, retrieves for each sub-query in parallel,
        and returns deduplicated results ranked by first-occurrence order.

        Args:
            query:           The original complex user query.
            retriever:       The retriever to use for each sub-query.
            top_k:           Number of results to fetch per sub-query.
            collection_name: Optional Qdrant collection override.

        Returns:
            Deduplicated list of Chunk objects, in order of first occurrence.
        """
        sub_queries = await self.decompose(query)

        # Execute all sub-query retrievals in parallel
        retrieve_tasks = [
            retriever.retrieve(
                query=sq,
                top_k=top_k,
                collection_name=collection_name,
            )
            for sq in sub_queries
        ]

        results_per_sub_query: list[list[Chunk]] = await asyncio.gather(*retrieve_tasks)

        # Deduplicate by chunk ID, preserving first-occurrence order
        seen_ids: set[str] = set()
        merged: list[Chunk] = []

        for chunks in results_per_sub_query:
            for chunk in chunks:
                if chunk.id not in seen_ids:
                    seen_ids.add(chunk.id)
                    merged.append(chunk)

        logger.info(
            f"Decomposed retrieval: {len(sub_queries)} sub-queries → "
            f"{sum(len(r) for r in results_per_sub_query)} raw → "
            f"{len(merged)} unique chunks"
        )

        return merged
