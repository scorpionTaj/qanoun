"""Vercel Python function: the whole FastAPI app behind one route (see vercel.json)."""

from qanoun_api.main import app

__all__ = ["app"]
