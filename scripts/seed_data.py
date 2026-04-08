import argparse
import asyncio
import time
from pathlib import Path

from app.config import settings
from app.core.exceptions import DuplicateDocumentError
from app.dependencies import get_ingestion_service, initialize_all, shutdown_all
from app.infrastructure.logging.structured import logger


async def seed_data(data_dirs: list[str], chunker: str, dry_run: bool):
    """Production seeder script targeting markdown and PDFs across nested directories."""
    valid_dirs = []
    
    for d in data_dirs:
        path = Path(d)
        if path.exists():
            valid_dirs.append(path)
        else:
            print(f"[WARNING] Directory path {d} does not exist. Skipping.")

    if not valid_dirs:
        print("❌ No valid root directories found. Terminating.")
        return

    # Temporarily override the configured chunker constraint if specified via CLI
    if chunker:
        settings.CHUNKER_STRATEGY = chunker

    print("\n🚀 Booting DeepVault Data Pipeline...")
    print(f"Target Directories: {[p.resolve().name for p in valid_dirs]}")
    print(f"Chunking Strategy: {settings.CHUNKER_STRATEGY}")
    print(f"Dry Run: {dry_run}\n")

    if dry_run:
        print("[DRY RUN] Will not initialize DB or write records.")
        
        files = []
        for d in valid_dirs:
            files.extend([f for ext in settings.SUPPORTED_FILE_EXTENSIONS for f in d.rglob(f"*{ext}")])
            
        print(f"Found {len(files)} supportive files matching {settings.SUPPORTED_FILE_EXTENSIONS}.")
        for f in files[:5]:  # Show first 5
            print(f" - {f.name}")
        if len(files) > 5:
            print(f" ... and {len(files) - 5} more.")
        return

    start_time = time.perf_counter()

    # We aggressively trigger dependency boot natively and synchronously for the background process
    await initialize_all()
    svc = await get_ingestion_service()

    files = []
    for d in valid_dirs:
        files.extend([f for ext in settings.SUPPORTED_FILE_EXTENSIONS for f in d.rglob(f"*{ext}")])
        
    total_files = len(files)

    pdf_count = 0
    md_txt_count = 0
    duplicate_count = 0
    success_count = 0
    failed_count = 0

    print(f"Found {total_files} files to process. Starting ingestion...\n")

    for i, file_path in enumerate(files, 1):
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            pdf_count += 1
        elif suffix in [".md", ".txt"]:
            md_txt_count += 1

        print(f"[{i}/{total_files}] Processing {file_path.name}...", end=" ", flush=True)

        try:
            doc = await svc.ingest_file(file_path)
            print(f"✅ Ingested ({doc.metadata.source})")
            success_count += 1
        except DuplicateDocumentError:
            print("⏭️  Already indexed, skipping.")
            duplicate_count += 1
        except Exception as e:
            print(f"❌ Failed: {str(e)}")
            logger.error(f"Seeder failed on {file_path}: {e}")
            failed_count += 1

    await shutdown_all()

    elapsed = time.perf_counter() - start_time
    print("\n=========================================")
    print(f"✅ Seeding Complete in {elapsed:.2f} seconds!")
    print(f"Total Files Formats: PDFs: {pdf_count} | MD/TXT: {md_txt_count}")
    print(f"Total Success: {success_count}")
    print(f"Total Skipped (Duplicates): {duplicate_count}")
    print(f"Total Failed: {failed_count}")
    print("=========================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeepVault local corpus bootstrapper")
    parser.add_argument("--data-dirs", nargs="+", default=settings.DATA_DIRS, help="Multiple parent directories containing data (space-separated)")
    parser.add_argument(
        "--chunker", type=str, choices=["fixed", "sliding", "semantic", "structure"], help="Override chunking strategy"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print stats without ingesting")

    args = parser.parse_args()

    # Due to SentenceTransformers and Async I/O, we secure the event loop dynamically here
    asyncio.run(seed_data(args.data_dirs, args.chunker, args.dry_run))
