.PHONY: test lint typecheck fmt ci publish serve

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

publish:
	uv run oh publish --metro nyc
	uv run oh publish --metro phl

serve:
	uv run oh serve

ci: lint typecheck test
