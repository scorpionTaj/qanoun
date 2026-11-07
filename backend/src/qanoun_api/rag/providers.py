"""LLM providers configured on the server, with automatic fallback between them.

Keys live in `.env` (never in the browser): the UI only picks a provider id and a model,
and the backend talks to the provider. Configure any of:

    QANOUN_LLM_URL / _MODEL / _KEY      local OpenAI-compatible server (LM Studio, Ollama)
    QANOUN_GEMINI_KEY      [_MODEL]     Google AI Studio (free tier)
    QANOUN_OPENROUTER_KEY  [_MODEL]     OpenRouter (free ":free" models)
    QANOUN_NVIDIA_KEY      [_MODEL]     NVIDIA NIM (free credits)
    QANOUN_LLM_PROVIDER                 preferred provider id (default: first cloud with a key)

Cloud models are not hard-coded: when no _MODEL is set, the provider's live /models list
is read and a current chat model picked (see `recommend_model`), so new releases are used
without a code change. A request that fails before the first token moves on to the next
configured provider, so one provider being down never blocks answering.
"""

import os
import re
import threading
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from qanoun_api.rag.llm import LLMClient, LLMError

MODELS_TTL = 600.0  # seconds a provider's /models list is reused
BUSY_TTL = 180.0  # seconds a model that answered 503/429 is skipped (unless nothing else)

# Extra request fields per provider. Gemini 2.5+/3.x think deeply by default: grounded
# answering from 5 given articles and one-line rewrites don't need it, and "low" cuts
# latency from ~1 min to seconds. Other providers reject unknown fields, so opt-in only.
_EXTRA = {"gemini": {"reasoning_effort": "low"}}


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    base_url: str
    api_key: str = ""
    model: str = ""  # pinned in .env; empty = recommend from the live list
    local: bool = False
    key_env: str = ""
    key_url: str = ""

    @property
    def configured(self) -> bool:
        return self.local or bool(self.api_key)


_CLOUD = [
    # id, label, base url, key page
    ("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
     "https://aistudio.google.com/apikey"),
    ("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "https://openrouter.ai/keys"),
    ("nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", "https://build.nvidia.com/"),
]


def load_providers(env: Mapping[str, str] = os.environ) -> list[Provider]:
    """All known providers, preferred one first (configured or not, for the settings UI)."""
    providers = [
        Provider(
            id="local",
            label="LM Studio / Ollama",
            base_url=env.get("QANOUN_LLM_URL", "http://localhost:1234/v1").rstrip("/"),
            api_key=env.get("QANOUN_LLM_KEY", ""),
            model=env.get("QANOUN_LLM_MODEL", ""),
            local=True,
            key_env="QANOUN_LLM_URL",
        )
    ]
    for pid, label, url, key_url in _CLOUD:
        prefix = f"QANOUN_{pid.upper()}"
        providers.append(
            Provider(
                id=pid, label=label, base_url=url,
                api_key=env.get(f"{prefix}_KEY", "").strip(),
                model=env.get(f"{prefix}_MODEL", "").strip(),
                key_env=f"{prefix}_KEY", key_url=key_url,
            )
        )
    preferred = env.get("QANOUN_LLM_PROVIDER", "").strip()
    if not any(p.id == preferred and p.configured for p in providers):
        # a cloud key in .env is a clear signal; otherwise the local server
        preferred = next((p.id for p in providers if not p.local and p.configured), "local")
    providers.sort(key=lambda p: p.id != preferred)
    return providers


# Never chat models: embeddings, speech, images, moderation…
_NOT_CHAT = re.compile(
    r"embed|tts|audio|speech|whisper|image|imagen|veo|vision-only|guard|reward|rerank|aqa"
    r"|moderation|transcribe|live|clip|parse|retriever|safety|research|computer-use|robotics",
    re.IGNORECASE,
)
_FAMILIES = ("llama-3.3-70b", "deepseek", "qwen", "gemma", "mistral", "llama")


def _version_key(model_id: str) -> tuple:
    """Natural sort key: gemini-2.5-flash > gemini-2.0-flash > gemini-1.5-flash."""
    return tuple(int(n) for n in re.findall(r"\d+", model_id))


def recommend_model(provider_id: str, ids: list[str]) -> str | None:
    """A sensible current default chat model from a provider's live model list."""
    chat = [i for i in ids if not _NOT_CHAT.search(i)]
    if not chat:
        return None
    if provider_id == "gemini":
        # newest stable "flash": fast, free-tier, strong Arabic; previews only as fallback
        flash = [i for i in chat if "flash" in i and "lite" not in i and "thinking" not in i]
        stable = [i for i in flash if "preview" not in i and "exp" not in i]
        pool = stable or flash or chat
        return max(pool, key=_version_key)
    if provider_id == "openrouter":
        pool = [i for i in chat if i.endswith(":free")] or chat
    else:
        pool = [i for i in chat if "instruct" in i] or chat
    for family in _FAMILIES:
        matches = [i for i in pool if family in i.lower()]
        if matches:
            return max(matches, key=_version_key)
    return pool[0]


def ranked_models(provider_id: str, ids: list[str], n: int = 3) -> list[str]:
    """The n best chat models in recommendation order (fallbacks when the best is busy)."""
    pool, ranked = list(ids), []
    while len(ranked) < n:
        best = recommend_model(provider_id, pool)
        if best is None:
            break
        ranked.append(best)
        pool.remove(best)
    return ranked


# Models tried per provider before moving to the next provider (busy model → sibling).
MODELS_PER_PROVIDER = 3


class ProviderUnavailable(LLMError):
    pass


class LLMRouter:
    """Routes chat calls to the configured providers, in preference order, with fallback."""

    def __init__(self, providers: list[Provider]):
        self.providers = providers
        self._clients: dict[tuple[str, str], LLMClient] = {}
        self._models: dict[str, tuple[float, list[str]]] = {}
        self._busy: dict[tuple[str, str], float] = {}  # (provider, model) -> skip until
        self._lock = threading.Lock()

    # ── lookup ────────────────────────────────────────────────────────────────
    def get(self, provider_id: str) -> Provider:
        for provider in self.providers:
            if provider.id == provider_id:
                if not provider.configured:
                    raise ProviderUnavailable(
                        f"{provider.label} has no API key — set {provider.key_env} in .env",
                        kind="auth",
                    )
                return provider
        raise ProviderUnavailable(f"unknown provider {provider_id!r}", kind="model")

    def configured(self) -> list[Provider]:
        return [p for p in self.providers if p.configured]

    @property
    def default(self) -> Provider:
        return self.configured()[0]  # local is always configured

    def models(self, provider_id: str) -> list[str]:
        """Live model list (cached); the recommended model first."""
        provider = self.get(provider_id)
        now = time.monotonic()
        with self._lock:
            cached = self._models.get(provider_id)
        if cached and now - cached[0] < MODELS_TTL:
            return cached[1]
        ids = sorted(set(self._client(provider, "").list_models()))
        top = ranked_models(provider.id, ids, MODELS_PER_PROVIDER)
        if provider.model:
            top = [provider.model, *[m for m in top if m != provider.model]]
        ordered = top + [i for i in ids if i not in top]
        with self._lock:
            self._models[provider_id] = (now, ordered)
        return ordered

    def resolve_model(self, provider: Provider, model: str = "") -> str:
        """Request model > .env model > recommended live model (local: auto-detect)."""
        if model or provider.model or provider.local:
            return model or provider.model
        models = self.models(provider.id)
        if not models:
            raise LLMError(f"{provider.label} lists no chat model", kind="model")
        return models[0]

    def _client(self, provider: Provider, model: str) -> LLMClient:
        key = (provider.id, model)
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = LLMClient(
                    base_url=provider.base_url, model=model, api_key=provider.api_key,
                    extra=_EXTRA.get(provider.id, {}),
                )
                self._clients[key] = client
            return client

    def _chain(self, provider_id: str | None, model: str) -> list[tuple[Provider, str]]:
        """Attempts in order: the requested provider and model first; if the model was left
        to us, the provider's next-best models (a busy model often has an idle sibling);
        then the other configured providers the same way."""
        first = self.get(provider_id) if provider_id else self.default
        rest = [p for p in self.configured() if p.id != first.id]
        attempts: list[tuple[Provider, str]] = []
        for provider, wanted in [(first, model), *[(p, "") for p in rest]]:
            if wanted or provider.local:
                attempts.append((provider, wanted))
                continue
            try:
                candidates = self.models(provider.id)[:MODELS_PER_PROVIDER]
            except LLMError:
                candidates = []
            # an empty name lets resolve_model raise the provider's own error in the loop
            attempts += [(provider, m) for m in candidates] or [(provider, "")]
        # Recently busy models go last instead of costing a failed round-trip every call.
        now = time.monotonic()
        with self._lock:
            busy = {key for key, until in self._busy.items() if until > now}
        return sorted(attempts, key=lambda a: (a[0].id, a[1]) in busy)

    def _mark(self, provider: Provider, model: str, exc: LLMError) -> None:
        if exc.kind in ("unavailable", "rate_limit") and model:
            with self._lock:
                self._busy[(provider.id, model)] = time.monotonic() + BUSY_TTL

    # ── calls ─────────────────────────────────────────────────────────────────
    def chat_stream(
        self, messages: list[dict], provider_id: str | None = None, model: str = "",
        on_start=None, **kwargs,
    ) -> Iterator[str]:
        """Stream from the first provider that produces a token. `on_start(provider, model)`
        is called once, before the first token, so callers can report who answered."""
        errors: list[LLMError] = []
        for provider, wanted in self._chain(provider_id, model):
            started = False
            try:
                resolved = self.resolve_model(provider, wanted)
                client = self._client(provider, resolved)
                for token in client.chat_stream(messages, **kwargs):
                    if not started:
                        started = True
                        if on_start:
                            on_start(provider, client.model or resolved)
                    yield token
                if started:
                    return
                errors.append(LLMError(f"{provider.label}: empty response", kind="empty"))
            except LLMError as exc:
                if started:
                    raise  # mid-answer failure: never splice another provider's text in
                self._mark(provider, wanted, exc)
                errors.append(LLMError(f"{provider.label}: {exc}", kind=exc.kind))
        raise _combined(errors)

    def chat(
        self, messages: list[dict], provider_id: str | None = None, model: str = "", **kwargs
    ) -> str:
        errors: list[LLMError] = []
        for provider, wanted in self._chain(provider_id, model):
            try:
                resolved = self.resolve_model(provider, wanted)
                return self._client(provider, resolved).chat(messages, **kwargs)
            except LLMError as exc:
                self._mark(provider, wanted, exc)
                errors.append(LLMError(f"{provider.label}: {exc}", kind=exc.kind))
        raise _combined(errors)

    def bind(self, provider_id: str | None = None, model: str = "") -> "BoundLLM":
        return BoundLLM(self, provider_id, model)

    def test(self, provider_id: str, model: str = "") -> dict:
        """One tiny completion against exactly this provider (no fallback)."""
        provider = self.get(provider_id)
        resolved = self.resolve_model(provider, model)
        client = self._client(provider, resolved)
        start = time.perf_counter()
        reply = client.chat([{"role": "user", "content": "Reply with: OK"}], max_tokens=200)
        return {
            "ok": True,
            "provider": provider.id,
            "model": client.model or resolved,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "reply": reply.strip()[:80],
        }


def _combined(errors: list[LLMError]) -> LLMError:
    """One error for the whole chain; its kind is the most actionable one seen."""
    kinds = [e.kind for e in errors]
    kind = next(
        (k for k in ("auth", "rate_limit", "unavailable", "model", "empty", "unreachable")
         if k in kinds),
        "error",
    )
    return LLMError(" | ".join(str(e) for e in errors) or "no LLM provider configured", kind=kind)


class BoundLLM:
    """The router with a fixed provider preference, shaped like LLMClient (chat/chat_stream)
    so the rewriter, the answerer and the eval harness need no provider logic."""

    def __init__(self, router: LLMRouter, provider_id: str | None, model: str):
        self.router = router
        self.provider_id = provider_id
        self.model = model

    def chat(self, messages: list[dict], **kwargs) -> str:
        return self.router.chat(messages, self.provider_id, self.model, **kwargs)

    def chat_stream(self, messages: list[dict], on_start=None, **kwargs) -> Iterator[str]:
        return self.router.chat_stream(
            messages, self.provider_id, self.model, on_start=on_start, **kwargs
        )


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter(load_providers())
    return _router


def set_router(router: LLMRouter | None) -> None:
    """Test seam."""
    global _router
    _router = router
