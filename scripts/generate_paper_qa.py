import asyncio
import json
import os
import re
from pathlib import Path
from typing import List, Dict

import fitz  # PyMuPDF
from app.config import settings
from app.infrastructure.llm.groq import GroqLLMClient
from app.infrastructure.logging.structured import logger

# Configuration for Generation
INPUT_DIR = Path("data/curated_papers")
OUTPUT_FILE = Path("data/research_papers_golden_qa.json")
QUESTIONS_PER_PAPER = 10
MAX_CONTENT_CHARS = 12000  # Approx 3000-4000 tokens to stay safe with Groq limits

SYSTEM_PROMPT = """You are an expert AI researcher. 
Your task is to generate {count} high-quality, technical Question and Answer pairs from the provided research paper text.

Requirements:
1. The questions should be specific and technical, covering methodology, results, or unique insights.
2. The answers must be grounded strictly in the provided text.
3. Provide the output as a JSON list of objects, each with "question", "answer", and "source_document" keys.
4. "source_document" should be the filename provided.

Example format:
[
  {{
    "question": "What specifically does the paper state about X?",
    "answer": "The paper states that X happens because of Y...",
    "source_document": "paper_name.pdf"
  }}
]
"""

USER_PROMPT_TEMPLATE = """Research Paper Filename: {filename}

Text Content (Excerpt):
---
{text}
---

Please generate {count} technical QA pairs based on the text above."""


class QAGenerator:
    def __init__(self):
        self.llm = GroqLLMClient()
        self.results = []

    def extract_text(self, pdf_path: Path) -> str:
        """Extracts text from PDF, prioritizing Abstract and Introduction if possible."""
        try:
            content = ""
            with fitz.open(pdf_path) as doc:
                # Extract first 6 pages which usually contain Abstract, Intro, and early methodology
                # and the last 2 pages for Conclusion/Discussions
                num_pages = len(doc)
                pages_to_read = list(range(min(6, num_pages)))
                if num_pages > 6:
                    pages_to_read.extend(range(max(num_pages - 2, 6), num_pages))
                
                for p_idx in pages_to_read:
                    content += doc[p_idx].get_text()
            
            # Truncate if still too long
            return content[:MAX_CONTENT_CHARS]
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""

    async def generate_for_paper(self, pdf_path: Path):
        filename = pdf_path.name
        
        # Check if already processed
        if any(r['source_document'] == filename for r in self.results):
            logger.info(f"Skipping {filename}, already processed.")
            return

        logger.info(f"Processing {filename}...")
        
        text = self.extract_text(pdf_path)
        if not text:
            logger.warning(f"No text extracted for {filename}, skipping.")
            return

        user_prompt = USER_PROMPT_TEMPLATE.format(
            filename=filename,
            text=text,
            count=QUESTIONS_PER_PAPER
        )
        
        system_prompt = SYSTEM_PROMPT.format(count=QUESTIONS_PER_PAPER)

        try:
            response = await self.llm.generate(prompt=user_prompt, system_prompt=system_prompt)
            # Try to parse JSON from response
            match = re.search(r"\[\s*\{.*\}\s*\]", response.answer, re.DOTALL)
            parsed_batch = []
            if match:
                parsed_batch = json.loads(match.group(0))
            else:
                try:
                    parsed_batch = json.loads(response.answer)
                except json.JSONDecodeError:
                    # Try to find anything between [ and ]
                    start = response.answer.find('[')
                    end = response.answer.rfind(']') + 1
                    if start != -1 and end != -1:
                        parsed_batch = json.loads(response.answer[start:end])

            if parsed_batch:
                self.results.extend(parsed_batch)
                logger.info(f"Successfully generated {len(parsed_batch)} QAs for {filename}")
                self.save_results()
            else:
                logger.error(f"Could not parse JSON from response for {filename}")
        except Exception as e:
            logger.error(f"Failed to generate QAs for {filename}: {e}")

    def save_results(self):
        """Save current results to disk."""
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

    def load_existing(self):
        """Load existing results if file exists."""
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    self.results = json.load(f)
                logger.info(f"Loaded {len(self.results)} existing QA pairs.")
            except Exception as e:
                logger.error(f"Failed to load existing results: {e}")

    async def run(self):
        if not INPUT_DIR.exists():
            logger.error(f"Input directory {INPUT_DIR} does not exist.")
            return

        self.load_existing()
        
        pdf_files = list(INPUT_DIR.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files.")

        # Sequential processing is slower but safer for rate limits and state management
        for i, pdf in enumerate(pdf_files):
            await self.generate_for_paper(pdf)
            # More generous sleep to avoid 429
            await asyncio.sleep(2)

        logger.info(f"Generation complete! Total QAs: {len(self.results)}")
        logger.info(f"Final output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    generator = QAGenerator()
    asyncio.run(generator.run())
