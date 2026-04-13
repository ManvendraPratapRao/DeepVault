"""
scripts/reset_db.py
-------------------
DeepVault database reset utility.

Modes:
  Full reset (all strategies):
    python -m scripts.reset_db

  Single strategy reset:
    python -m scripts.reset_db --strategy semantic
    python -m scripts.reset_db --strategy fixed
"""

import argparse
import asyncio
import sqlite3
from pathlib import Path

from qdrant_client import AsyncQdrantClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH    = "deepvault.db"
QDRANT_URL = "http://localhost:6333"
ALL_STRATEGIES = ["fixed", "sliding", "structure", "semantic"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_sqlite(strategies: list[str]):
    """Remove document rows matching the given strategies from SQLite."""
    if not Path(DB_PATH).exists():
        print(f"[SKIP] SQLite file '{DB_PATH}' not found.")
        return

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if set(strategies) == set(ALL_STRATEGIES):
        # Full wipe — faster than per-strategy delete
        cursor.execute("DELETE FROM documents")
        deleted = cursor.rowcount
        print(f"[OK]  SQLite: cleared all documents ({deleted} rows)")
    else:
        for strategy in strategies:
            cursor.execute(
                "DELETE FROM documents WHERE metadata->>'$.chunking_strategy' = ?;",
                (strategy,),
            )
            print(f"[OK]  SQLite: cleared '{strategy}' rows ({cursor.rowcount} deleted)")

    conn.commit()
    conn.close()


async def _clear_qdrant(strategies: list[str]):
    """Delete Qdrant collections for the given strategies."""
    client = AsyncQdrantClient(url=QDRANT_URL)

    for strategy in strategies:
        coll = f"deepvault_{strategy}"
        try:
            await client.delete_collection(coll)
            print(f"[OK]  Qdrant: deleted collection '{coll}'")
        except Exception as e:
            print(f"[WARN] Qdrant: could not delete '{coll}': {e}")

    await client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def reset(strategies: list[str]):
    label = "ALL" if set(strategies) == set(ALL_STRATEGIES) else ", ".join(strategies).upper()
    print(f"\n[RESET] Starting DeepVault reset — scope: {label}\n")

    _clear_sqlite(strategies)
    await _clear_qdrant(strategies)

    print("\n[SUCCESS] Reset complete. Ready for fresh re-indexing.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DeepVault database reset tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=ALL_STRATEGIES,
        default=None,
        help="Reset only a specific chunking strategy (omit for full reset)",
    )

    args = parser.parse_args()
    targets = [args.strategy] if args.strategy else ALL_STRATEGIES

    asyncio.run(reset(targets))
