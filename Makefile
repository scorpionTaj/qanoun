# Qanoun — one entry point for the whole lifecycle.
#
#   make db        start postgres (docker)          make ingest   run the full DE pipeline
#   make api       start the FastAPI backend        make web      start the Next.js frontend
#   make dev       db + api + web together          make eval     run the eval harness
#   make test      all offline tests                make clean    remove processed artifacts

SHELL := /bin/bash
-include .env
export

DB_URL      ?= postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun
PYPIPE      := uv run --project pipeline
PYAPI       := uv run --project backend

.PHONY: help db db-stop api web dev ingest eval test lint clean ingest-pipeline migrate

help:
	@grep -E '^# ' $(MAKEFILE_LIST) | cut -c3-

# ── Infrastructure ──────────────────────────────────────────────────────────────

db:
	docker compose up -d db
	@echo "postgres ready on localhost:5433 (user qanoun, db qanoun)"

db-stop:
	docker compose down

# ── Data engineering pipeline ───────────────────────────────────────────────────

# fetch PDFs (skips files already present), then parse → structure → chunk → embed → load
ingest:
	$(PYPIPE) python -m qanoun_pipeline.cli ingest-all

ingest-pipeline:
	$(PYPIPE) python -m qanoun_pipeline.cli ingest-all --skip-fetch

migrate:
	$(PYAPI) alembic upgrade head

# ── Services ────────────────────────────────────────────────────────────────────

api:
	$(PYAPI) uvicorn qanoun_api.main:app --reload --port 8000

web:
	cd frontend && npm run dev

# db + api + web in three panes via your terminal; docker must be running.
dev:
	@echo "Run in separate terminals:"; echo "  make db"; echo "  make api"; echo "  make web"

# ── Quality & evaluation ────────────────────────────────────────────────────────

test:
	$(PYPIPE) pytest pipeline/tests -q
	$(PYAPI) pytest backend/tests -q
	cd frontend && npx tsc --noEmit

lint:
	$(PYPIPE) ruff check pipeline backend
	cd frontend && npx next lint || true

# Retrieval + grounded-answer evaluation (needs the LLM endpoint running).
eval:
	$(PYAPI) python -m qanoun_api.eval.run --report docs/eval-report.md

# ── Cleanup ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf data/processed/* data/ocr/*
	@echo "processed artifacts removed (raw PDFs kept)"
