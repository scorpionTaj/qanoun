"""What this server does with personal data, for the privacy notice (law 09-08, art. 5).

The notice's wording lives in the clients; this endpoint supplies the facts that depend on the
deployment: who runs it, the CNDP receipt, which outside services receive questions (and
where they are, art. 43), and how long logs are kept.
"""

from fastapi import APIRouter

from qanoun_api import accounts, querylog
from qanoun_api.config import SETTINGS
from qanoun_api.rag.providers import get_router

router = APIRouter(prefix="/api", tags=["privacy"])

# Outside services by provider id: who they are and where they process data.
_PROCESSORS = {
    "gemini": ("Google (Gemini API)", "United States"),
    "openrouter": ("OpenRouter", "United States"),
    "nvidia": ("NVIDIA (NIM API)", "United States"),
    "jina": ("Jina AI (embeddings / reranking)", "Germany"),
}


@router.get("/privacy")
def privacy():
    configured = [p.id for p in get_router().configured()]
    uses_jina = SETTINGS.embed_model.startswith("jina") or SETTINGS.reranker.startswith("jina")
    processors = [
        {"id": pid, "name": _PROCESSORS[pid][0], "country": _PROCESSORS[pid][1]}
        for pid in [*configured, *(["jina"] if uses_jina else [])]
        if pid in _PROCESSORS
    ]
    return {
        "controller": SETTINGS.privacy_controller or None,
        "contact": SETTINGS.privacy_contact or None,
        "cndp_receipt": SETTINGS.cndp_receipt or None,
        "processors": processors,  # services outside Morocco that receive the question text
        "local_model": "local" in configured,
        "accounts": SETTINGS.allow_signup,
        "query_log": {"question_text": SETTINGS.log_questions, "retention_days": querylog.RETENTION_DAYS},
        "session_days": accounts.SESSION_DAYS,
    }
