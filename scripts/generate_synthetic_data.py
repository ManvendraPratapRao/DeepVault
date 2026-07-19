"""
scripts/generate_synthetic_data.py
====================================
Generates expanded synthetic enterprise knowledge-base documents and
a refreshed golden Q&A dataset for DeepVault using Groq LLMs.

Strategy
--------
• Generates ~145 new markdown documents across 7 document categories
  for 7 fictional enterprise projects (deepvault, chimera, nexus, atlas,
  aurora, sentinel, titan) to bring the corpus from ~105 to ~250 docs.
• Generates 200 new golden Q&A pairs (from new docs only) to bring the
  golden dataset from 100 to ~300 entries.
• Rotates across 4 Groq models to stay within per-model daily limits.

Models used
-----------
  llama-3.1-8b-instant          → bulk doc generation (6K TPM, 30 RPM)
  meta-llama/llama-4-scout-17b-16e-instruct → high-quality docs (30K TPM)
  qwen/qwen3-32b                → backup doc gen (6K TPM, 60 RPM)
  llama-3.3-70b-versatile       → Q&A generation only (12K TPM, quality)

Usage
-----
  uv run python scripts/generate_synthetic_data.py

Outputs
-------
  synthetic_data_v2/{category}/   — new .md files appended
  synthetic_data_v2/golden_qa_dataset.json — merged & deduped
  synthetic_data_v2/manifest.json — updated file list
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from groq import Groq

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# -- project root on path ------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Groq client ───────────────────────────────────────────────────────────────


def _load_env_key() -> str:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise ValueError("GROQ_API_KEY not found in environment or .env file")


client = Groq(api_key=os.environ.get("GROQ_API_KEY") or _load_env_key())


# ── constants ─────────────────────────────────────────────────────────────────
SYNTHETIC_DIR = ROOT / "synthetic_data_v2"
GOLDEN_QA_PATH = SYNTHETIC_DIR / "golden_qa_dataset.json"
MANIFEST_PATH = SYNTHETIC_DIR / "manifest.json"

PROJECTS = ["deepvault", "chimera", "nexus", "atlas", "aurora", "sentinel", "titan"]

CATEGORIES = {
    "slack_conversations": 50,
    "project_docs": 50,
    "meeting_notes": 40,
    "wiki_pages": 40,
    "incident_reports": 40,
    "api_documentation": 40,
    "runbooks_sops": 30,
}

# Model rotation: (model_id, max_tokens_per_call, delay_between_calls_sec)
MODELS = [
    ("meta-llama/llama-4-scout-17b-16e-instruct", 1200, 2.1),
    ("llama-3.1-8b-instant", 900, 2.1),
    ("qwen/qwen3-32b", 900, 1.1),
    ("openai/gpt-oss-120b", 1200, 2.1),
    ("openai/gpt-oss-20b", 1000, 2.1),
    ("qwen/qwen3.6-27b", 1000, 2.1),
    ("llama-3.3-70b-versatile", 1200, 2.1),  # Q&A only
]

QA_MODEL = "llama-3.3-70b-versatile"
QA_MODEL_DELAY = 2.2

RANDOM_SEED = 42
rng = random.Random(RANDOM_SEED)

# ── prompt templates ──────────────────────────────────────────────────────────

CATEGORY_PROMPTS = {
    "slack_conversations": """\
Write a realistic Slack channel conversation (15-25 messages) between 3-5 engineers
at OmniSynapse Corp about {project}. Topics: architecture decisions, debugging a
production issue, code reviews, deployment discussions, or performance problems.
Use realistic Slack formatting: timestamps like [09:34], @mentions, code blocks,
and emoji reactions. Each message should be 1-4 sentences.
Output ONLY the conversation markdown, no intro text.
Title the document: # Slack: #{project}-engineering — {topic}
""",
    "project_docs": """\
Write a detailed technical project specification document (600-900 words) for
{project} at OmniSynapse Corp. Include: Overview, Architecture, Key Components,
Data Flow, Dependencies, Performance Requirements, and Open Questions sections.
Use realistic technical details: specific frameworks, databases, APIs, metrics.
Output ONLY the markdown document.
Title: # {project} — Technical Specification v{version}
""",
    "meeting_notes": """\
Write realistic engineering meeting notes (400-600 words) for a {project} team
at OmniSynapse Corp. Include: Date, Attendees (3-5 names), Agenda items,
Discussion points with technical depth, Action items with owners and deadlines,
and a summary of decisions made.
Output ONLY the markdown notes document.
Title: # {project} Engineering Sync — {date}
""",
    "wiki_pages": """\
Write a detailed internal wiki page (600-900 words) about {project} at OmniSynapse
Corp. The page should cover one of: system architecture, onboarding guide,
troubleshooting playbook, data model reference, or API integration guide.
Include headers, bullet points, code examples, and internal cross-references.
Output ONLY the markdown wiki page.
Title: # {project} Wiki: {topic}
""",
    "incident_reports": """\
Write a realistic post-mortem incident report (500-700 words) for a production
incident in {project} at OmniSynapse Corp. Include: Incident Summary, Timeline
(with specific times), Root Cause Analysis, Impact Assessment, Immediate Actions
Taken, Long-term Remediation, and Lessons Learned.
Use specific technical details (error codes, services, stack traces).
Output ONLY the markdown report.
Title: # Incident Report: {project} — {incident_type} ({date})
""",
    "api_documentation": """\
Write realistic REST API documentation (500-700 words) for a {project} service
at OmniSynapse Corp. Document 3-5 endpoints including: method, path, description,
request body schema, response schema, error codes, and 1-2 curl examples.
Use realistic field names and data types. Include authentication details.
Output ONLY the markdown API docs.
Title: # {project} API Reference — {service_name} Service
""",
    "runbooks_sops": """\
Write a detailed operational runbook / SOP (400-600 words) for {project} at
OmniSynapse Corp. Include: Purpose, Prerequisites, Step-by-step procedure
(numbered, with exact commands), Verification steps, Rollback procedure,
and On-call escalation contacts.
Output ONLY the markdown runbook.
Title: # Runbook: {project} — {operation}
""",
}

TOPIC_VARIANTS = {
    "slack_conversations": [
        "deployment pipeline failure",
        "database migration planning",
        "API rate limit issues",
        "model performance degradation",
        "security vulnerability response",
        "infrastructure scaling",
        "on-call handoff",
        "data pipeline latency spike",
        "new feature rollout",
        "dependency upgrade breaking changes",
        "memory leak investigation",
        "cache invalidation bug",
    ],
    "project_docs": ["v1.0", "v1.1", "v2.0", "v2.1", "v3.0"],
    "meeting_notes": [
        "June 2, 2025",
        "June 9, 2025",
        "June 16, 2025",
        "June 23, 2025",
        "July 7, 2025",
        "July 14, 2025",
        "July 21, 2025",
    ],
    "wiki_pages": [
        "Architecture Overview",
        "Getting Started Guide",
        "Troubleshooting Playbook",
        "Data Model Reference",
        "Deployment Guide",
        "Configuration Reference",
        "Security Best Practices",
        "Performance Tuning",
    ],
    "incident_reports": [
        "Database Outage",
        "API Gateway Failure",
        "Memory Leak in Production",
        "Data Pipeline Corruption",
        "Authentication Service Degradation",
        "Cache Stampede",
        "Kafka Consumer Lag Spike",
        "Vector DB Connection Pool Exhaustion",
    ],
    "api_documentation": [
        "Data Ingestion",
        "Model Serving",
        "User Management",
        "Analytics",
        "Authentication",
        "Notification",
        "Search",
        "Storage",
    ],
    "runbooks_sops": [
        "Database Failover",
        "Blue-Green Deployment",
        "Rollback Procedure",
        "Cache Warm-Up",
        "Certificate Rotation",
        "Incident Response",
        "Capacity Scaling",
        "Log Rotation",
    ],
    "incident_dates": [
        "2025-01-15",
        "2025-02-03",
        "2025-03-22",
        "2025-04-11",
        "2025-05-07",
        "2025-06-19",
        "2024-11-30",
        "2024-12-14",
    ],
}


# ── helpers ───────────────────────────────────────────────────────────────────


def _next_doc_index(category_dir: Path, project: str) -> int:
    """Find the next available numeric suffix for this project in this category."""
    existing = list(category_dir.glob(f"project_{project}_*.md"))
    if not existing:
        return 1
    indices = []
    for f in existing:
        m = re.search(r"_(\d+)\.md$", f.name)
        if m:
            indices.append(int(m.group(1)))
    return max(indices) + 1 if indices else 1


def _model_iterator() -> Iterator[tuple[str, int, float]]:
    """Round-robin over the doc-generation models (excludes QA model)."""
    doc_models = MODELS[:-1]
    idx = 0
    while True:
        yield doc_models[idx % len(doc_models)]
        idx += 1


def _call_groq(model: str, prompt: str, max_tokens: int, delay: float) -> str:
    """Call Groq with basic retry logic."""
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.85,
            )
            time.sleep(delay)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            wait = 2**attempt * 5
            print(f"  [RETRY {attempt + 1}] {model}: {e} — waiting {wait}s")
            time.sleep(wait)
    return ""


def _build_prompt(category: str, project: str) -> str:
    template = CATEGORY_PROMPTS[category]
    topic_list = TOPIC_VARIANTS.get(category, ["general"])
    topic = rng.choice(topic_list)
    date = rng.choice(TOPIC_VARIANTS["meeting_notes"])
    incident_date = rng.choice(TOPIC_VARIANTS["incident_dates"])
    incident_type = rng.choice(TOPIC_VARIANTS["incident_reports"])
    version = rng.choice(TOPIC_VARIANTS["project_docs"])
    service_name = rng.choice(TOPIC_VARIANTS["api_documentation"])
    operation = rng.choice(TOPIC_VARIANTS["runbooks_sops"])

    return template.format(
        project=f"Project {project.capitalize()}",
        topic=topic,
        date=date,
        incident_date=incident_date,
        incident_type=incident_type,
        version=version,
        service_name=service_name,
        operation=operation,
    )


def _generate_qa_for_doc(doc_content: str, source_doc_name: str, n: int = 2) -> list[dict]:
    """Generate n Q&A pairs grounded in a specific document."""
    prompt = f"""You are creating a golden Q&A dataset for evaluating a RAG system.

Given this internal enterprise document:

---
{doc_content[:3000]}
---

Generate exactly {n} question-answer pairs that:
1. Can ONLY be answered using information explicitly present in this document
2. Are realistic questions an employee might ask an internal knowledge base
3. Have specific, factual answers (not vague or general)
4. Cover different parts of the document
5. The question should NOT mention "the document" or "according to" — phrase it naturally

Output ONLY a JSON array with this exact format:
[
  {{"question": "...", "answer": "...", "source_document": "{source_doc_name}"}},
  {{"question": "...", "answer": "...", "source_document": "{source_doc_name}"}}
]

Output ONLY the JSON array. No other text."""

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=QA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7,
            )
            time.sleep(QA_MODEL_DELAY)
            raw = resp.choices[0].message.content.strip()

            # Extract JSON array from the response
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                pairs = json.loads(match.group())
                if isinstance(pairs, list) and pairs:
                    return pairs
        except Exception as e:
            wait = 2**attempt * 5
            print(f"  [QA RETRY {attempt + 1}] {e} — waiting {wait}s")
            time.sleep(wait)

    return []


# ── main generation ───────────────────────────────────────────────────────────


def generate_documents() -> list[tuple[str, Path]]:
    """Generate all new documents. Returns list of (source_doc_name, file_path)."""
    model_gen = _model_iterator()
    generated: list[tuple[str, Path]] = []
    total_planned = sum(CATEGORIES.values())
    done = 0

    # Build a work list: (category, project) pairs distributed evenly
    work_list: list[tuple[str, str]] = []
    for category, count in CATEGORIES.items():
        category_dir = SYNTHETIC_DIR / category
        category_dir.mkdir(exist_ok=True)
        for _ in range(count):
            project = rng.choice(PROJECTS)
            work_list.append((category, project))

    rng.shuffle(work_list)

    for category, project in work_list:
        model, max_tokens, delay = next(model_gen)
        category_dir = SYNTHETIC_DIR / category
        idx = _next_doc_index(category_dir, project)
        filename = f"project_{project}_{idx}.md"
        filepath = category_dir / filename
        source_name = f"project_{project}_{idx}"

        print(f"[{done + 1}/{total_planned}] {model.split('/')[-1][:20]:20s} → {category}/{filename}")

        prompt = _build_prompt(category, project)
        content = _call_groq(model, prompt, max_tokens, delay)

        if not content:
            print(f"  [SKIP] Empty response for {filename}")
            done += 1
            continue

        filepath.write_text(content, encoding="utf-8")
        generated.append((source_name, filepath))
        done += 1

    print(f"\n✅ Generated {len(generated)}/{total_planned} documents.")
    return generated


def generate_qa_pairs(generated_docs: list[tuple[str, Path]], qa_per_doc: int = 2) -> list[dict]:
    """Generate golden Q&A pairs for newly created documents."""
    all_pairs: list[dict] = []
    total = len(generated_docs)

    for i, (source_name, filepath) in enumerate(generated_docs):
        print(f"[QA {i + 1}/{total}] Generating {qa_per_doc} pairs for {source_name}")
        content = filepath.read_text(encoding="utf-8")
        pairs = _generate_qa_for_doc(content, source_name, n=qa_per_doc)
        all_pairs.extend(pairs)

    print(f"\n✅ Generated {len(all_pairs)} Q&A pairs from {total} documents.")
    return all_pairs


def merge_and_save_qa(new_pairs: list[dict]) -> None:
    """Merge new pairs with existing golden dataset, dedup, save."""
    existing: list[dict] = []
    if GOLDEN_QA_PATH.exists():
        existing = json.loads(GOLDEN_QA_PATH.read_text(encoding="utf-8"))
        print(f"[QA] Existing dataset: {len(existing)} entries")

    # Deduplicate by question text (normalised)
    seen_questions: set[str] = set()
    merged: list[dict] = []

    for item in existing + new_pairs:
        q_norm = re.sub(r"\s+", " ", str(item.get("question", "")).lower().strip())
        if q_norm and q_norm not in seen_questions:
            seen_questions.add(q_norm)
            # Normalise answer: flatten list to string
            raw_answer = item.get("answer", "")
            answer = " ".join(raw_answer) if isinstance(raw_answer, list) else str(raw_answer).strip()
            merged.append(
                {
                    "question": item.get("question", ""),
                    "answer": answer,
                    "source_document": item.get("source_document", ""),
                }
            )

    GOLDEN_QA_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[QA] Saved {len(merged)} total Q&A pairs → {GOLDEN_QA_PATH.name}")


def update_manifest() -> None:
    """Rebuild manifest.json from all current .md files in synthetic_data_v2/."""
    paths: list[str] = []
    for category_dir in sorted(SYNTHETIC_DIR.iterdir()):
        if not category_dir.is_dir() or category_dir.name.startswith("."):
            continue
        for md_file in sorted(category_dir.glob("*.md")):
            rel = str(md_file.relative_to(ROOT))
            paths.append(rel)

    MANIFEST_PATH.write_text(json.dumps(paths, indent=2), encoding="utf-8")
    print(f"[MANIFEST] Updated with {len(paths)} files → {MANIFEST_PATH.name}")


# ── entrypoint ────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n" + "=" * 65)
    print("  DeepVault Synthetic Data Generator")
    print(f"  Target: ~{sum(CATEGORIES.values())} new documents + Q&A pairs")
    print("=" * 65 + "\n")

    # Phase 1: Generate documents
    print("-- Phase 1: Document Generation -----------------------------------\n")
    generated = generate_documents()

    # Phase 2: Generate Q&A pairs
    print("\n-- Phase 2: Q&A Generation ----------------------------------------\n")
    new_pairs = generate_qa_pairs(generated, qa_per_doc=2)

    # Phase 3: Merge + save golden dataset
    print("\n-- Phase 3: Merging Golden Dataset --------------------------------\n")
    merge_and_save_qa(new_pairs)

    # Phase 4: Update manifest
    update_manifest()

    print("\n" + "=" * 65)
    print("  ✅ Generation Complete!")
    print(f"  Documents generated : {len(generated)}")
    print(f"  New QA pairs        : {len(new_pairs)}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
