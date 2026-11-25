"""Qanoun API entry point.

    uv run --project backend uvicorn qanoun_api.main:app --reload --port 8000
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from qanoun_pipeline.load_db import ensure_schema

from qanoun_api import __version__, mcp_server
from qanoun_api.config import SETTINGS
from qanoun_api.db import close_pool, db
from qanoun_api.rag.retrieval import get_embedder
from qanoun_api.routers import analytics, auth, chat, conversations, keys, laws, llm, search


def _warm_up() -> None:
    try:
        get_embedder().encode_query("warm-up")
    except Exception:
        logging.getLogger(__name__).exception("embedding model warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema lives in qanoun_pipeline.schema: numbered migrations, applied once each.
    with db() as conn:
        applied = ensure_schema(conn)
    if applied:
        logging.getLogger(__name__).info("applied schema migrations %s", applied)
    # Load the embedding model in the background: the API is up immediately, and the
    # first question no longer waits ~10-30 s for BGE-M3 to load.
    threading.Thread(target=_warm_up, name="embedder-warmup", daemon=True).start()
    async with mcp_server.running():  # the MCP endpoint's transport, one per lifespan
        yield
    close_pool()


app = FastAPI(
    title="Qanoun API",
    description="Moroccan legal texts: explore, search and ask — grounded in the sources.",
    version=__version__,
    lifespan=lifespan,
    docs_url="/",  # the API's home page is its interactive documentation (Swagger UI)
    swagger_ui_parameters={"persistAuthorization": True},  # keep an entered API key on reload
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
app.include_router(keys.router)
# MCP for AI agents (streamable HTTP at /mcp), see qanoun_api.mcp_server.
# POST only: stateless, there is no server stream to GET (a 405 tells clients so at once;
# a GET used to stay open until the function timed out) and no session to DELETE.
app.add_route("/mcp", mcp_server.endpoint, methods=["POST"], include_in_schema=False)


@app.get("/docs", include_in_schema=False)
def docs_redirect():
    """The docs moved to `/`; keep the conventional path working."""
    return RedirectResponse("/")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


def _openapi() -> dict:
    """The generated schema plus /mcp, a raw ASGI route FastAPI cannot describe itself, so the
    Swagger UI can call the MCP tools too (JSON-RPC 2.0, one request per call)."""
    if app.openapi_schema is None:
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        schema["paths"]["/mcp"] = mcp_server.OPENAPI_PATH
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _openapi
