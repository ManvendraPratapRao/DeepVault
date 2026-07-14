# Contributing to DeepVault

We welcome contributions to DeepVault! This document outlines our development workflow, coding standards, and testing strategy.

## Development Setup

1. **Install uv:** We use `uv` for lightning-fast Python package management.
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. **Clone and Sync:**
   ```bash
   git clone https://github.com/ManvendraPratapRao/DeepVault.git
   cd DeepVault
   uv sync
   ```
3. **Pre-commit Hooks:** (Optional but recommended)
   Run `make lint-fix` before committing to format code with `ruff`.

## Architecture Rules

DeepVault strictly follows a Hexagonal Architecture. When adding new features:
1. **Never** put business logic in FastAPI routes (`app/api/`).
2. **Never** make `app/core/` depend on `app/infrastructure/`.
3. If you add a new database or LLM provider, create a concrete class in `app/infrastructure/` that implements the relevant ABC in `app/core/interfaces/`.
4. Register your new implementation in the dependency injection container (`app/dependencies.py`).

## Testing Strategy

We use `pytest` with custom markers to separate fast unit tests from slow integration/eval tests.

- `@pytest.mark.unit`: Pure unit tests. No network calls, no databases. Must execute in milliseconds. These run on every CI push.
- `@pytest.mark.integration`: Tests that require Qdrant and Redis to be running.
- `@pytest.mark.eval`: Full RAG pipeline tests that hit the live Groq API. These cost money and take time, so they are run manually.

**Running Tests:**
```bash
# Run only fast unit tests
uv run pytest -m "unit"

# Run everything except live LLM calls
uv run pytest -m "not eval"
```

## Pull Request Process

1. Create a feature branch (`feat/your-feature` or `fix/your-fix`).
2. Ensure `make lint` and `make typecheck` pass.
3. Write unit tests for your changes.
4. If modifying the retrieval pipeline or chunking logic, you **must** run the evaluation engine (`make eval`) and include the before/after Faithfulness and Hallucination metrics in your PR description.
5. Submit the PR for review.
