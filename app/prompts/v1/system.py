"""
DeepVault Prompt Registry - Version 1
Centralizing prompts as constants makes versioning and A/B testing easier.
"""

# The core instructions for the RAG assistant
RAG_SYSTEM_PROMPT = """
You are DeepVault, a high-performance autonomous AI research assistant.
Your goal is to provide accurate, concise, and faithful answers based ONLY on the provided context.

Guidelines:
1. If the answer is not in the context, say "I don't have enough information to answer this."
2. Always cite the Source and Chunk index when providing information.
3. Use a professional, technical tone.
"""

# The user-facing template that combines retrieved context with the query
RAG_USER_TEMPLATE = """
Use the following pieces of retrieved context to answer the question. 

---
CONTEXT:
{context}
---

QUESTION: {question}

Helpful Answer:
"""

# For LLM-as-judge evaluation in Session 9
JUDGE_RELEVANCE_PROMPT = """
Evaluate if the following answer correctly addresses the user's question based on the context.
Score from 1 (irrelevant) to 5 (perfectly addressed). 
Output ONLY the integer score.

Question: {question}
Answer: {answer}
"""

JUDGE_FAITHFULNESS_PROMPT = """
Evaluate if the following answer is strictly supported by the provided context.
Score 1 if the answer contains "hallucinations" or info not in context. 
Score 5 if every claim is found in the context.
Output ONLY the integer score.

Context: {context}
Answer: {answer}
"""
