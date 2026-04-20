from app.core.interfaces.llm_client import BaseLLMClient
from app.core.interfaces.rewriter import BaseQueryRewriter
from app.infrastructure.logging.structured import logger
from app.prompts.v2.query_rewrite import QUERY_REWRITE_SYSTEM_PROMPT, QUERY_REWRITE_USER_TEMPLATE


class GroqQueryRewriter(BaseQueryRewriter):
    """
    Implementation of the BaseQueryRewriter using the Groq LLM client.
    Expands user queries to improve retrieval grounding.
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def rewrite(self, query: str) -> str:
        """
        Calls the LLM to rewrite and expand the input query.
        """
        logger.info(f"Rewriting query: '{query}'")

        # Build the prompt using the V2 template
        prompt = QUERY_REWRITE_USER_TEMPLATE.replace("{query}", query)

        try:
            # Generate the expanded query
            result = await self.llm_client.generate(prompt=prompt, system_prompt=QUERY_REWRITE_SYSTEM_PROMPT)

            rewritten_query = result.answer.strip()

            # Sanity check: Ensure the model didn't return an empty string
            if not rewritten_query:
                logger.warning("Query rewriter returned empty result. Falling back to original query.")
                return query

            logger.info(f"Query expanded to: '{rewritten_query}'")
            return rewritten_query

        except Exception as e:
            logger.error(f"Query rewriting failed: {e}. Falling back to original query.")
            return query
