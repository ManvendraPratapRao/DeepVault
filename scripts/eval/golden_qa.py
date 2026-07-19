"""
eval/golden_qa.py
=================
Loads and validates the Golden QA dataset for evaluation.
"""

import json
import logging
from dataclasses import dataclass

from .config import SYNTHETIC_QA_PATH

logger = logging.getLogger(__name__)


@dataclass
class QAPair:
    question: str
    answer: str
    source_document: str


def load_golden_dataset(limit: int | None = None) -> list[QAPair]:
    """Loads the golden dataset from disk and optionally limits the size."""
    if not SYNTHETIC_QA_PATH.exists():
        raise FileNotFoundError(f"Golden dataset not found at {SYNTHETIC_QA_PATH}")

    with open(SYNTHETIC_QA_PATH, encoding="utf-8") as f:
        raw_data = json.load(f)

    dataset = []
    for item in raw_data:
        if "question" in item and "answer" in item and "source_document" in item:
            dataset.append(
                QAPair(question=item["question"], answer=item["answer"], source_document=item["source_document"])
            )

    if limit:
        # We can shuffle to ensure random distribution, but fixed is fine for now
        dataset = dataset[:limit]

    logger.info(f"Loaded {len(dataset)} QA pairs from golden dataset.")
    return dataset
