.PHONY: test lint typecheck fmt ci

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run pyright

fmt:
	uv run ruff check --fix src tests
	uv run ruff format src tests

ci: lint typecheck test
