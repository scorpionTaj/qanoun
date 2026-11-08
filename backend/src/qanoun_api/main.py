"""Qanoun API entry point.

    uv run --project backend uvicorn qanoun_api.main:app --reload --port 8000
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from qanoun_pipeline.load_db import ensure_schema

from qanoun_api import __version__
from qanoun_api.accounts import ensure_app_schema
from qanoun_api.config import SETTINGS
from qanoun_api.db import close_pool, db
from qanoun_api.rag.retrieval import get_embedder
from qanoun_api.routers import analytics, auth, chat, conversations, laws, llm, search


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
        ensure_app_schema(conn)  # accounts + synced conversations
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
    allow_origins=list(SETTINGS.cors_origins),
    allow_credentials=True,  # session cookie for optional accounts
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if SETTINGS.cookie_secure:  # served over HTTPS
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.include_router(laws.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(llm.router)
app.include_router(auth.router)
app.include_router(conversations.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}
