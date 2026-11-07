"""LLM provider endpoints for the settings dialog: what is configured, which models a
provider offers, and a one-click connection test. Keys are never returned."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from qanoun_api.rag.llm import LLMError
from qanoun_api.rag.providers import ProviderUnavailable, get_router

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/providers")
def providers():
    llm = get_router()
    return {
        "default": llm.default.id,
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "configured": p.configured,
                "local": p.local,
                "model": p.model,  # pinned in .env, or "" for auto
                "key_env": p.key_env,  # which .env variable enables it
                "key_url": p.key_url,
                "base_url": p.base_url if p.local else None,
            }
            for p in llm.providers
        ],
    }


@router.get("/providers/{provider_id}/models")
def models(provider_id: str):
    try:
        ids = get_router().models(provider_id)
    except ProviderUnavailable as exc:
        raise HTTPException(400, {"code": exc.kind, "message": str(exc)}) from exc
    except LLMError as exc:
        raise HTTPException(502, {"code": exc.kind, "message": str(exc)[:400]}) from exc
    return {"provider": provider_id, "recommended": ids[0] if ids else None, "models": ids}


class TestRequest(BaseModel):
    provider: str = Field(pattern=r"^[a-z]{2,20}$")
    model: str = Field(default="", max_length=200)


@router.post("/test")
def test(req: TestRequest):
    try:
        return get_router().test(req.provider, req.model)
    except LLMError as exc:
        return {"ok": False, "provider": req.provider, "code": exc.kind, "message": str(exc)[:400]}
