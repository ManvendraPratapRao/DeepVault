"""
scripts/fix_ragas_vertexai.py
==============================
One-time patch for ragas 0.2.9 / 0.4.x compatibility issue where
ragas.llms.base unconditionally imports langchain_community.chat_models.vertexai
which was removed in langchain-community 0.4.x.

Run once after `uv sync` or after recreating the venv:
    uv run python scripts/fix_ragas_vertexai.py
"""

import pathlib
import sys

BASE_PY = pathlib.Path(".venv/Lib/site-packages/ragas/llms/base.py")

OLD_IMPORT = (
    "from langchain_community.chat_models.vertexai import ChatVertexAI\nfrom langchain_community.llms import VertexAI"
)

NEW_IMPORT = (
    "try:\n"
    "    from langchain_community.chat_models.vertexai import ChatVertexAI\n"
    "    from langchain_community.llms import VertexAI\n"
    "except ImportError:\n"
    "    ChatVertexAI = None\n"
    "    VertexAI = None"
)


def main() -> None:
    if not BASE_PY.exists():
        print(f"[SKIP] {BASE_PY} not found — ragas may not be installed yet.")
        sys.exit(0)

    src = BASE_PY.read_text(encoding="utf-8")

    if OLD_IMPORT not in src:
        print("[OK] Patch already applied or not needed.")
        sys.exit(0)

    patched = src.replace(OLD_IMPORT, NEW_IMPORT)
    BASE_PY.write_text(patched, encoding="utf-8")
    print("[PATCHED] ragas.llms.base — ChatVertexAI import made optional.")


if __name__ == "__main__":
    main()
