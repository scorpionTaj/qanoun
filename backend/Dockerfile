FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install the API plus the shared pipeline package it depends on.
COPY backend/pyproject.toml backend/uv.lock* backend/
COPY pipeline/ /app/pipeline/

WORKDIR /app/backend
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

COPY backend/src ./src

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "qanoun_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
