"""Qanoun API entry point.

    uv run --project backend uvicorn qanoun_api.main:app --reload --port 8000
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qanoun_pipeline.load_db import ensure_schema

from qanoun_api import __version__
from qanoun_api.db import close_pool, db
from qanoun_api.rag.retrieval import get_embedder
from qanoun_api.routers import analytics, chat, laws, llm, search


def _warm_up() -> None:
    try:
        get_embedder().encode_query("warm-up")
    except Exception:
        logging.getLogger(__name__).exception("embedding model warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema lives in qanoun_pipeline.schema (single source of truth, idempotent).
    with db() as conn:
        ensure_schema(conn)
    # Load the embedding model in the background: the API is up immediately, and the
    # first question no longer waits ~10-30 s for BGE-M3 to load.
    threading.Thread(target=_warm_up, name="embedder-warmup", daemon=True).start()
    yield
    close_pool()


app = FastAPI(
    title="Qanoun API",
    description="Moroccan legal texts: explore, search and ask — grounded in the sources.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(laws.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(llm.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}
