FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "oh"]
