"""Streaming grounded chat over the legal corpus (Server-Sent Events).

Event flow per POST /api/chat:
    meta     {variety, rewritten, disclaimer}   — always first
    sources  {sources: [...]}                   — the k retrieved passages (citation targets)
    token    {t: "…"}                           — streamed answer tokens
    done     {abstained, cited: [n...]}         — parse_citations over the full text
    error    {message}

The answer is generated ONLY from the retrieved sources (see rag/answer.py); when they do
not contain the answer the model replies NO_ANSWER and the UI shows the abstention text.
"""

import json
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from qanoun_api.config import SETTINGS
from qanoun_api.rag import answer as answer_mod
from qanoun_api.rag import retrieval
from qanoun_api.rag.answer import ABSTENTION, DISCLAIMER, NO_ANSWER, build_messages, parse_citations
from qanoun_api.rag.llm import LLMClient, strip_reasoning
from qanoun_api.rag.rewrite import QueryRewriter, detect_variety

router = APIRouter(prefix="/api", tags=["chat"])

_llm: LLMClient | None = None
_rewriter: QueryRewriter | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient(base_url=SETTINGS.llm_url, model=SETTINGS.llm_model, api_key=SETTINGS.llm_key)
    return _llm


def get_rewriter() -> QueryRewriter:
    global _rewriter
    if _rewriter is None:
        _rewriter = QueryRewriter(get_llm(), cache_path=SETTINGS.rewrite_cache)
    return _rewriter


def set_llm(llm: LLMClient | None, rewriter: QueryRewriter | None = None) -> None:
    """Test seam."""
    global _llm, _rewriter
    _llm = llm
    _rewriter = rewriter


class LLMConfig(BaseModel):
    """Per-request LLM override: any OpenAI-compatible endpoint (LM Studio, OpenRouter,
    Google Gemini's OpenAI layer, NVIDIA NIM…). The key lives in the browser and is used
    for this request only — the backend never stores it."""

    base_url: str = Field(min_length=8, max_length=300)
    model: str = Field(default="", max_length=200)
    api_key: str = Field(default="", max_length=400)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    llm: LLMConfig | None = None


def _client_for(req: ChatRequest) -> LLMClient:
    if req.llm:
        return LLMClient(
            base_url=req.llm.base_url.rstrip("/"),
            model=req.llm.model,
            api_key=req.llm.api_key,
        )
    return get_llm()


def _rewriter_for(req: ChatRequest) -> QueryRewriter:
    if req.llm:
        # A browser-supplied endpoint must not write into the shared on-disk cache: its
        # rewrites would then be served to every other user.
        return QueryRewriter(_client_for(req), cache_path=None)
    return get_rewriter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chat_stream(req: ChatRequest) -> Iterator[str]:
    question = req.question.strip()
    variety = detect_variety(question)
    llm = _client_for(req)
    try:
        rewriter = _rewriter_for(req)
        rewritten = rewriter.rewrite(question)
    except Exception:  # rewriting is an optimization; never block answering on it
        rewritten = question
    yield _sse("meta", {"variety": variety, "rewritten": rewritten, "disclaimer": DISCLAIMER[variety]})

    try:
        result = retrieval.search(question, k=req.k, search_query=rewritten)
        if rewritten != question:
            # Keep the original question's results too: a bad rewrite must not lose hits.
            original = retrieval.search(question, k=req.k)
            result = answer_mod.merge(original, result, req.k)
    except Exception as exc:
        yield _sse("error", {"message": f"retrieval failed: {exc}"})
        return

    yield _sse("sources", {"sources": [hit.as_dict() for hit in result.hits]})
    if not result.hits:
        yield _sse("done", {"abstained": True, "cited": [], "text": ABSTENTION[variety]})
        return

    messages = build_messages(question, result.hits, variety)
    chunks: list[str] = []
    try:
        for token in llm.chat_stream(messages, max_tokens=600):
            chunks.append(token)
            yield _sse("token", {"t": token})
    except Exception as exc:
        if not chunks:
            yield _sse("error", {"message": f"LLM unavailable: {exc}"})
            return
        # The stream broke mid-answer: never present a truncated legal answer as complete.
        yield _sse("error", {"message": f"LLM stream interrupted: {exc}"})
        return
    text = strip_reasoning("".join(chunks)).strip()
    if NO_ANSWER in text or not text:
        yield _sse("done", {"abstained": True, "cited": [], "text": ABSTENTION[variety]})
        return
    yield _sse("done", {"abstained": False, "cited": parse_citations(text, len(result.hits)), "text": text})


@router.post("/chat")
def chat(req: ChatRequest):
    return StreamingResponse(
        _chat_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
