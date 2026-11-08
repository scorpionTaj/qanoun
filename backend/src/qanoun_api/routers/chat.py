"""Streaming grounded chat over the legal corpus (Server-Sent Events).

Event flow per POST /api/chat:
    status   {stage: rewriting|searching|answering} — progress, several times
    meta     {variety, rewritten, disclaimer}   — once the rewrite is known
    sources  {sources: [...]}                   — the k retrieved passages (citation targets)
    model    {provider, provider_label, model}  — which provider answered (before 1st token)
    token    {t: "…"}                           — streamed answer tokens
    done     {abstained, cited: [n...], text, timings} — final text, citations, ms per step
    error    {code, message}                    — code: unreachable | auth | rate_limit |
                                                  model | empty | interrupted | retrieval

The answer is generated ONLY from the retrieved sources (see rag/answer.py); when they do
not contain the answer the model replies NO_ANSWER and the UI shows the abstention text.
"""

import json
import logging
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from qanoun_api.config import SETTINGS
from qanoun_api.rag import answer as answer_mod
from qanoun_api.rag import retrieval
from qanoun_api.rag.answer import ABSTENTION, DISCLAIMER, NO_ANSWER, build_messages, parse_citations
from qanoun_api.rag.llm import LLMError, strip_reasoning
from qanoun_api.rag.providers import ProviderUnavailable, get_router
from qanoun_api.rag.rewrite import QueryRewriter, condense, detect_variety
from qanoun_api.ratelimit import chat_limit

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger("qanoun.chat")

# Room for reasoning models (Gemini 2.5+, DeepSeek) whose hidden thinking counts against
# max_tokens; the prompt still caps the visible answer at 4 sentences.
ANSWER_TOKENS = 1500

_llm_override = None  # test seam: anything with chat()/chat_stream()
_rewriter: QueryRewriter | None = None


def get_rewriter() -> QueryRewriter:
    """One rewriter (and one on-disk cache) for all requests: every provider is configured
    server-side, so a cached rewrite is trustworthy whichever model produced it."""
    global _rewriter
    if _rewriter is None:
        _rewriter = QueryRewriter(get_router().bind(), cache_path=SETTINGS.rewrite_cache)
    return _rewriter


def set_llm(llm, rewriter: QueryRewriter | None = None) -> None:
    """Test seam: replace the provider router with a fake LLM."""
    global _llm_override, _rewriter
    _llm_override = llm
    _rewriter = rewriter


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    # Which server-configured provider/model to prefer (see GET /api/llm/providers).
    # Never a URL or a key: those stay in .env.
    provider: str | None = Field(default=None, pattern=r"^[a-z]{2,20}$")
    model: str = Field(default="", max_length=200)
    # Where the answer may come from: one legal domain, or one law (all its editions).
    # Both empty = the whole corpus.
    domain: str | None = Field(default=None, pattern=r"^[a-z]{2,30}$")
    group: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    # Recent turns of this conversation (oldest first) so follow-ups like «and for women?»
    # work. Capped: context, not a transcript.
    history: list[Turn] = Field(default_factory=list, max_length=6)
    # Answer settings (⚙): length and language. "auto" = the question's own language.
    style: Literal["concise", "detailed"] = "concise"
    answer_language: Literal["auto", "ar", "fr", "en"] = "auto"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chat_stream(req: ChatRequest) -> Iterator[str]:
    question = req.question.strip()
    variety = detect_variety(question)
    if _llm_override is not None:
        llm = _llm_override
    else:
        try:
            if req.provider:
                get_router().get(req.provider)  # unknown or key-less provider → clear error now
            llm = get_router().bind(req.provider, req.model)
        except ProviderUnavailable as exc:
            yield _sse("error", {"code": exc.kind, "message": str(exc)})
            return
    timings: dict[str, int] = {}
    clock = time.perf_counter()

    def lap(name: str) -> None:
        nonlocal clock
        now = time.perf_counter()
        timings[name] = round((now - clock) * 1000)
        clock = now

    # The rewrite (an LLM call, Darija/Arabizi only) and the search for the original question
    # don't depend on each other: run them at the same time.
    needs_rewrite = variety in ("darija", "arabizi")
    yield _sse("status", {"stage": "rewriting" if needs_rewrite else "searching"})
    rewriter = _rewriter or get_rewriter()
    history = [turn.model_dump() for turn in req.history]
    if history:
        # A follow-up is searched as a standalone question; the user's own wording still
        # drives the answer's language.
        yield _sse("status", {"stage": "rewriting"})
        try:
            standalone = condense(question, history, llm)
        except Exception:  # noqa: BLE001 — fall back to the literal follow-up
            standalone = question
    else:
        standalone = question
    with ThreadPoolExecutor(max_workers=2) as pool:
        scope = {"domain": req.domain, "group": req.group}
        original_future = pool.submit(retrieval.search, standalone, k=req.k, **scope)
        rewrite_future = pool.submit(rewriter.rewrite, standalone, llm=llm)
        try:
            rewritten = rewrite_future.result()
        except Exception:  # noqa: BLE001 — rewriting is an optimization; never block answering
            rewritten = standalone
        lap("rewrite")
        yield _sse("meta", {"variety": variety, "rewritten": rewritten, "disclaimer": DISCLAIMER[variety]})
        if needs_rewrite:
            yield _sse("status", {"stage": "searching"})
        try:
            result = original_future.result()
            if rewritten != standalone:
                # Merge both runs: a bad rewrite can only add hits, never lose them.
                rewritten_result = retrieval.search(standalone, k=req.k, search_query=rewritten, **scope)
                result = answer_mod.merge(result, rewritten_result, req.k)
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as an SSE error event
            yield _sse("error", {"code": "retrieval", "message": f"retrieval failed: {exc}"})
            return
    lap("search")

    yield _sse("sources", {"sources": [hit.as_dict() for hit in result.hits]})
    if not result.hits:
        yield _sse("done", {"abstained": True, "cited": [], "text": ABSTENTION[variety]})
        return

    yield _sse("status", {"stage": "answering"})
    messages = build_messages(question, result.hits, variety, history, req.style, req.answer_language)
    answered_by: dict = {}

    def on_start(provider, model: str) -> None:
        answered_by.update(provider=provider.id, provider_label=provider.label, model=model)

    stream = (
        llm.chat_stream(messages, max_tokens=ANSWER_TOKENS, on_start=on_start)
        if _llm_override is None
        else llm.chat_stream(messages, max_tokens=ANSWER_TOKENS)
    )
    chunks: list[str] = []
    try:
        for token in stream:
            if not chunks and answered_by:
                yield _sse("model", answered_by)
            chunks.append(token)
            yield _sse("token", {"t": token})
    except Exception as exc:  # noqa: BLE001 — surfaced to the client as an SSE error event
        code = exc.kind if isinstance(exc, LLMError) else "error"
        if chunks:
            # The stream broke mid-answer: never present a truncated legal answer as complete.
            code = "interrupted"
        yield _sse("error", {"code": code, "message": str(exc)[:600]})
        return
    lap("answer")
    log.info("chat timings ms %s via %s", timings, answered_by.get("model", "?"))
    text = strip_reasoning("".join(chunks)).strip()
    if not text:
        yield _sse("error", {"code": "empty", "message": "the model returned an empty answer"})
        return
    if NO_ANSWER in text:
        yield _sse("done", {"abstained": True, "cited": [], "text": ABSTENTION[variety],
                            "timings": timings, **answered_by})
        return
    yield _sse(
        "done",
        {"abstained": False, "cited": parse_citations(text, len(result.hits)), "text": text,
         "timings": timings, **answered_by},
    )


@router.post("/chat", dependencies=[Depends(chat_limit)])
def chat(req: ChatRequest):
    return StreamingResponse(
        _chat_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
