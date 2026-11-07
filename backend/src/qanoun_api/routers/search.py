"""Hybrid search endpoint: pgvector + Arabic FTS, fused, with citation-ready results."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from qanoun_api.rag import retrieval
from qanoun_api.rag.rewrite import detect_variety

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=500)
    domain: str | None = None
    law_slug: str | None = None
    k: int = Field(default=8, ge=1, le=50)


@router.post("/search")
def search(req: SearchRequest):
    result = retrieval.search(req.q, k=req.k, domain=req.domain, law_slug=req.law_slug)
    return {
        "query": result.query,
        "search_query": result.search_query,
        "variety": detect_variety(req.q),
        "results": [hit.as_dict() for hit in result.hits],
    }
