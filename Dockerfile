FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data/published ./data/published

RUN uv sync --frozen --no-dev

ENV OH_DATA_DIR=/app/data
ENV OH_PUBLISHED_DIR=/app/data/published

EXPOSE 8080
ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "oh"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
