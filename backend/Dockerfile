# Build from the repo root (the API depends on the pipeline package next to it):
#   docker build -f backend/Dockerfile .                           # slim: remote embeddings (Jina)
#   docker build -f backend/Dockerfile --build-arg EXTRAS=models . # + PyTorch for local BGE-M3
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ARG EXTRAS=""

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Dependencies first (cached until a lockfile changes), then the sources.
COPY pipeline/ /app/pipeline/
COPY backend/pyproject.toml backend/uv.lock /app/backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project ${EXTRAS:+--extra $EXTRAS}
COPY backend/src ./src
RUN uv sync --frozen --no-dev ${EXTRAS:+--extra $EXTRAS}

ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "qanoun_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
