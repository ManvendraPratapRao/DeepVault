import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path to allow imports from app
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings
from app.dependencies import clear_cache
from scripts.seed_data import seed_data

STRATEGIES = ["fixed", "sliding", "structure", "semantic"]


async def run_all_strategies():
    """
    Orchestrates a 4-pass ingestion loop across all major chunking strategies.
    Ensures that each strategy is indexed into its own isolated Qdrant collection.
    """
    print("🚀 Starting DeepVault Master Seeding Pipeline (Isolated Pass)")
    print(f"Targeting {len(STRATEGIES)} strategies: {STRATEGIES}\n")

    total_start_time = time.perf_counter()

    for strategy in STRATEGIES:
        print(f"\n{'='*50}")
        print(f"📡 PASS: {strategy.upper()}")
        print(f"{'='*50}")

        # 1. Clear singleton cache to ensure fresh dependency instantiation (Chunker & Vector Store)
        clear_cache()

        # 2. Update global settings purely for this pass
        settings.CHUNKER_STRATEGY = strategy

        try:
            # 3. Trigger the pass
            # We target the specific curated and synthetic folders for Phase 1
            await seed_data(
                data_dirs=["synthetic_data_v2", "data/curated_papers"],
                chunker=strategy,
                dry_run=False
            )
        except Exception as e:
            print(f"❌ Critical failure during {strategy} pass: {e}")
            # We continue to the next strategy even if one fails
            continue

    total_elapsed = time.perf_counter() - total_start_time
    print(f"\n✨ MASTER SEEDING COMPLETE in {total_elapsed:.2f} seconds!")
    print("Check your Qdrant dashboard at http://localhost:6333 for the 4 isolated collections.")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_strategies())
    except KeyboardInterrupt:
        print("\n🛑 Master seeding aborted by user.")
        sys.exit(0)
