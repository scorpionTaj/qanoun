# Qanoun — one entry point for the whole lifecycle.
#
#   make db        start postgres (docker)          make ingest   full DE pipeline → Postgres
#   make api       start the FastAPI backend        make web      start the Next.js frontend
#   make dev       how to run all three             make eval     retrieval + LLM-judge evaluation
#   make test      all offline tests                make clean    remove processed artifacts

SHELL := /bin/bash
-include .env
export

DB_URL      ?= postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun
PYPIPE      := uv run --project pipeline
PYPIPE_MODELS := uv run --project pipeline --extra models
PYAPI       := uv run --project backend
PYAPI_MODELS := uv run --project backend --extra models

.PHONY: help db db-stop api web dev ingest ingest-smoke eval test lint clean

help:
	@grep -E '^# ' $(MAKEFILE_LIST) | cut -c3-

# ── Infrastructure ──────────────────────────────────────────────────────────────

db:
	docker compose up -d db
	@echo "postgres ready on localhost:5433 (user qanoun, db qanoun)"

db-stop:
	docker compose down

# ── Data engineering pipeline ───────────────────────────────────────────────────

# fetch PDFs (skips present files) → parse (OCR fallback) → structure → chunk → embed → load
ingest:
	$(PYPIPE_MODELS) python -m qanoun_pipeline.cli ingest-all

# same pipeline with hash-based embeddings — proves the plumbing without the model download
ingest-smoke:
	$(PYPIPE) python -m qanoun_pipeline.cli ingest-all --skip-fetch --fake-embed

# ── Services ────────────────────────────────────────────────────────────────────

# --reload-dir: watching the whole repo restarted the API on every frontend build
api:
	$(PYAPI_MODELS) uvicorn qanoun_api.main:app --port 8000 --reload \
		--reload-dir backend/src --reload-dir pipeline/src

web:
	cd frontend && npm run dev

# db + api + web in three terminals; docker must be running.
dev:
	@echo "Run in separate terminals:"; echo "  make db"; echo "  make api"; echo "  make web"

# ── Quality & evaluation ────────────────────────────────────────────────────────

test:
	$(PYPIPE) pytest pipeline/tests -q
	$(PYAPI) pytest backend/tests -q
	cd frontend && npx tsc --noEmit

lint:
	$(PYPIPE) ruff check pipeline/src pipeline/tests backend/src backend/tests

# Retrieval metrics + grounded answers + LLM-as-judge (needs the LLM endpoint running).
eval:
	$(PYAPI_MODELS) python -m qanoun_api.eval.run --report docs/eval-report.md

eval-retrieval:
	$(PYAPI_MODELS) python -m qanoun_api.eval.run --retrieval-only --report docs/eval-report.md

# ── Cleanup ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf data/processed/* data/ocr/*
	@echo "processed artifacts removed (raw PDFs kept)"
