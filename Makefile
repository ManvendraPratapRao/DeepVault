.PHONY: run dev test test-cov seed eval lint lint-fix typecheck docker-up docker-down

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn app.main:app --reload --port 8000

test:
	uv run pytest -v --tb=short

test-cov:
	uv run pytest --cov=app --cov-report=term-missing

seed:
	PYTHONPATH=. uv run python scripts/seed_data.py

seed-all:
	PYTHONPATH=. uv run python scripts/seed_all.py

eval:
	uv run python scripts/run_eval.py

lint:
	uv run ruff check app/ tests/

lint-fix:
	uv run ruff check --fix app/ tests/
	uv run ruff format app/ tests/

typecheck:
	uv run mypy app/ || true

docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker compose -f docker/docker-compose.yml down
