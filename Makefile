.PHONY: run dev ui test test-cov seed seed-all eval reset count diagnose lint lint-fix typecheck docker-up docker-down

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn app.main:app --reload --port 8000

ui:
	uv run streamlit run app/ui/dashboard.py


test:
	uv run pytest -v --tb=short

test-cov:
	uv run pytest --cov=app --cov-report=term-missing

# Seed a single strategy: make seed CHUNKER=recursive
seed:
	PYTHONPATH=. uv run python scripts/seed.py --chunker $(or $(CHUNKER),sliding)

# Run the full 4-strategy master seeding pipeline
seed-all:
	PYTHONPATH=. uv run python scripts/seed.py --all-strategies

# Run the evaluation benchmark engine
eval:
	PYTHONPATH=. uv run python scripts/eval/runner_v2.py --limit 50 --run-id latest

# Reset all data. Single-strategy: make reset STRATEGY=semantic
reset:
	PYTHONPATH=. uv run python scripts/reset_db.py $(if $(STRATEGY),--strategy $(STRATEGY),)

# Check Qdrant point counts across all strategy collections
count:
	PYTHONPATH=. uv run python scripts/check_qdrant_counts.py

# Run chunk quality diagnostics across curated papers
diagnose:
	PYTHONPATH=. uv run python scripts/diagnostic_chunk_quality.py

lint:
	uv run ruff check app/ tests/ scripts/

lint-fix:
	uv run ruff check --fix app/ tests/ scripts/
	uv run ruff format app/ tests/ scripts/

typecheck:
	uv run mypy app/

docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker compose -f docker/docker-compose.yml down
