"""
eval/ragas_adapter.py
=====================
Converts DeepVault RAG responses into the HuggingFace Dataset format required by RAGAS.
"""

from typing import Any

from app.core.models.query import QueryResponse


def to_ragas_row(question: str, response: QueryResponse, ground_truth: str) -> dict[str, Any]:
    """
    Format for RAGAS evaluation.
    Requires:
    - user_input: The user's question
    - response: The generated answer
    - retrieved_contexts: List of strings (the chunks)
    - reference: The ground truth answer
    """
    return {
        "user_input": question,
        "response": response.answer,
        "retrieved_contexts": [chunk.content for chunk in response.sources],
        "reference": ground_truth,
    }
