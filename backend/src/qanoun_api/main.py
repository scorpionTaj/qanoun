"""Qanoun API entry point.

    uv run --project backend uvicorn qanoun_api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qanoun_api import __version__
from qanoun_api.db import close_pool, db
from qanoun_api.routers import analytics, chat, laws, search
from qanoun_pipeline.load_db import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema lives in qanoun_pipeline.schema (single source of truth, idempotent).
    with db() as conn:
        ensure_schema(conn)
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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}
