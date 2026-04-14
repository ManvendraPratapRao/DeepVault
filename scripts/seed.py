"""
scripts/seed.py
---------------
DeepVault corpus seeder.

Modes:
  Single strategy (default):
    python -m scripts.seed --chunker fixed

  All 4 strategies in sequence (master seeding pipeline):
    python -m scripts.seed --all-strategies

  Dry run (no actual ingestion):
    python -m scripts.seed --chunker fixed --dry-run
    python -m scripts.seed --all-strategies --dry-run

  Custom data directories:
    python -m scripts.seed --chunker fixed --data-dirs data/curated_papers synthetic_data_v2
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings
from app.core.exceptions import DuplicateDocumentError
from app.dependencies import clear_cache, get_ingestion_service, initialize_all, shutdown_all
from app.infrastructure.logging.structured import logger

ALL_STRATEGIES = ["fixed", "sliding", "structure", "semantic"]

# Per-strategy chunker configuration used in --all-strategies mode
STRATEGY_CONFIG = {
    "fixed": {"size": 500, "overlap": 100},
    "sliding": {"size": 800, "overlap": 250},
    "structure": {"size": 1000, "overlap": 200},
    "semantic": {"size": 500, "overlap": 100},  # size used only as fallback
}


# ---------------------------------------------------------------------------
# Core worker
# ---------------------------------------------------------------------------


async def _ingest_with_semaphore(svc, file_path: Path, semaphore: asyncio.Semaphore, stats: dict):
    """Worker task that respects a semaphore to limit concurrency."""
    async with semaphore:
        try:
            doc, chunk_count = await svc.ingest_file(file_path)
            print(f"[OK]   Ingested: {doc.metadata.source} ({chunk_count} chunks)")
            stats["success"] += 1
        except DuplicateDocumentError:
            print(f"[SKIP] {file_path.name} (Already indexed)")
            stats["duplicate"] += 1
        except Exception as e:
            print(f"[FAIL] {file_path.name} — {e}")
            logger.error(f"Seeder failed on {file_path}: {e}")
            stats["failed"] += 1


# ---------------------------------------------------------------------------
# Single-strategy pass
# ---------------------------------------------------------------------------


async def seed_single(data_dirs: list[str], chunker: str, dry_run: bool):
    """Run one ingestion pass for a specific chunker strategy."""
    valid_dirs = [Path(d) for d in data_dirs if Path(d).exists()]
    missing = [d for d in data_dirs if not Path(d).exists()]

    for m in missing:
        print(f"[WARNING] Directory '{m}' not found. Skipping.")

    if not valid_dirs:
        print("[ERROR] No valid directories found. Aborting.")
        return

    # Apply per-strategy chunker params if known
    if chunker in STRATEGY_CONFIG:
        cfg = STRATEGY_CONFIG[chunker]
        settings.CHUNKER_SIZE = cfg["size"]
        settings.CHUNKER_OVERLAP = cfg["overlap"]

    files = [f for d in valid_dirs for ext in settings.SUPPORTED_FILE_EXTENSIONS for f in d.rglob(f"*{ext}")]

    pdf_count = sum(1 for f in files if f.suffix.lower() == ".pdf")
    md_count = sum(1 for f in files if f.suffix.lower() in {".md", ".txt"})

    print(f"\n[CONFIG] Strategy: {chunker.upper()}")
    print(f"[CONFIG] Dirs:     {[p.resolve().name for p in valid_dirs]}")
    print(f"[CONFIG] Size/Overlap: {settings.CHUNKER_SIZE}/{settings.CHUNKER_OVERLAP}")
    print(f"[FOUND]  {len(files)} files  (PDFs: {pdf_count} | MD/TXT: {md_count})")

    if dry_run:
        print(f"[DRY RUN] Would ingest {len(files)} file(s). First: {files[0].name if files else 'N/A'}")
        return

    start = time.perf_counter()
    await initialize_all()
    svc = await get_ingestion_service(strategy=chunker)

    stats = {"success": 0, "duplicate": 0, "failed": 0}
    # Semaphore of 2 is stable for memory-intensive semantic chunking
    semaphore = asyncio.Semaphore(2)
    await asyncio.gather(*[_ingest_with_semaphore(svc, f, semaphore, stats) for f in files])

    await shutdown_all()
    elapsed = time.perf_counter() - start

    print("\n========================================")
    print(f"[DONE]  Completed in {elapsed:.2f}s")
    print(f"        Success:    {stats['success']}")
    print(f"        Duplicates: {stats['duplicate']}")
    print(f"        Failed:     {stats['failed']}")
    print("========================================\n")


# ---------------------------------------------------------------------------
# All-strategies orchestrator (was seed_all.py)
# ---------------------------------------------------------------------------


async def seed_all_strategies(data_dirs: list[str], dry_run: bool):
    """Run 4 sequential ingestion passes — one per chunking strategy."""
    print("[START] DeepVault Master Seeding Pipeline")
    print(f"        Strategies: {ALL_STRATEGIES}\n")

    total_start = time.perf_counter()

    for strategy in ALL_STRATEGIES:
        print(f"\n{'=' * 52}")
        print(f"  PASS: {strategy.upper()}")
        print(f"{'=' * 52}")

        # Reset singleton cache so each pass gets a fresh chunker + vector store
        clear_cache()

        try:
            await seed_single(data_dirs=data_dirs, chunker=strategy, dry_run=dry_run)
        except Exception as e:
            print(f"[ERROR] Critical failure during {strategy} pass: {e}")
            continue  # Move on to next strategy

    total_elapsed = time.perf_counter() - total_start
    print(f"\n[COMPLETE] Master seeding finished in {total_elapsed:.2f}s")
    print("Check Qdrant at http://localhost:6333 for all 4 isolated collections.")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DeepVault corpus seeder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--chunker",
        type=str,
        choices=ALL_STRATEGIES,
        default=None,
        help="Chunking strategy for a single-pass run",
    )
    parser.add_argument(
        "--all-strategies",
        action="store_true",
        help="Run all 4 strategies sequentially (master pipeline)",
    )
    parser.add_argument(
        "--data-dirs",
        nargs="+",
        default=["data/curated_papers", "synthetic_data_v2"],
        help="Root directories to scan for ingestible files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print file counts without actually ingesting",
    )

    args = parser.parse_args()

    if args.all_strategies:
        try:
            asyncio.run(seed_all_strategies(args.data_dirs, args.dry_run))
        except KeyboardInterrupt:
            print("\n[STOP] Master seeding aborted.")
            sys.exit(0)
    elif args.chunker:
        asyncio.run(seed_single(args.data_dirs, args.chunker, args.dry_run))
    else:
        parser.error("Specify --chunker <strategy> or --all-strategies")
