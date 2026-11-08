"""Minimal client for one OpenAI-compatible chat endpoint: LM Studio, Ollama, vLLM,
OpenRouter, Gemini's OpenAI layer, NVIDIA NIM (ported from darija-rag). Which endpoints
exist, their keys and the fallback between them live in rag/providers.py.

Model auto-detection builds an ordered candidate list — loaded models with a known chat
architecture first, then other loaded models, then the server's listed models — and tries
each until one answers. This survives LM Studio quirks like a non-chat model (e.g. a
speech model with arch=None) sitting loaded while the real LLMs are unloaded. Every error
carries the endpoint's response body, so "returned 400" always says WHY.
"""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import httpx

DEFAULT_URL = "http://localhost:1234/v1"


class ChatModel(Protocol):
    """What the answerer, rewriter and eval need: an LLMClient or a provider-router binding
    (qanoun_api.rag.providers.BoundLLM)."""

    def chat(self, messages: list[dict], **kwargs) -> str: ...


class LLMError(RuntimeError):
    """`kind` lets callers react without parsing text: unreachable | auth | rate_limit |
    unavailable | model | error. The UI maps it to a translated, actionable message."""

    def __init__(self, message: str, kind: str = "error", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


def _kind_for(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limit"
    if status in (400, 404, 422):
        return "model"
    if status in (502, 503, 504, 529):
        return "unavailable"  # provider overloaded: another model/provider may work now
    return "error"


@dataclass
class LLMClient:
    base_url: str = DEFAULT_URL
    model: str = ""  # explicit override from env; empty = auto-detect
    api_key: str = ""
    # Max silence between bytes: answers start within seconds on a healthy provider, so a
    # minute of nothing means it's down — fail and let the router/UI react, don't hang.
    timeout: float = 45.0
    extra: dict = field(default_factory=dict)  # provider-specific body fields
    _http: httpx.Client | None = field(default=None, repr=False)

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._http = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._http

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise LLMError(
                f"LLM endpoint {self.base_url} is unreachable ({exc.__class__.__name__}). "
                "Start the LM Studio server (Developer tab) or set QANOUN_LLM_URL.",
                kind="unreachable",
            ) from exc
        if response.status_code >= 400:
            raise LLMError(
                f"LLM endpoint returned {response.status_code}: {response.text[:300]}",
                kind=_kind_for(response.status_code),
                status=response.status_code,
            )
        return response.json()

    def list_models(self) -> list[str]:
        """Model ids the endpoint advertises (Gemini prefixes them with "models/")."""
        data = self._request("GET", "/models").get("data", [])
        return [str(m["id"]).removeprefix("models/") for m in data if m.get("id")]

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def _candidate_models(self) -> list[str]:
        """Ordered model candidates: LM Studio loaded models (known chat archs first),
        then everything else the server lists that is not an embedding model."""
        if self.model:
            return [self.model]
        candidates: list[str] = []
        root = self.base_url.removesuffix("/v1")
        try:
            data = self.http.get(f"{root}/api/v0/models", timeout=5).json().get("data", [])
        except (httpx.HTTPError, ValueError):
            data = []  # not LM Studio
        loaded = [m for m in data if m.get("state") == "loaded" and m.get("type") in ("llm", "vlm")]
        # a known arch means a real LLM; arch=None models (speech adapters etc.) may not chat
        loaded.sort(key=lambda m: m.get("arch") is None)
        candidates += [m["id"] for m in loaded]
        try:
            listed = self._request("GET", "/models").get("data", [])
            candidates += [
                m["id"]
                for m in listed
                if "embed" not in m["id"].lower() and m["id"] not in candidates
            ]
        except LLMError:
            pass
        return candidates

    def chat(self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 600) -> str:
        candidates = self._candidate_models()
        if not candidates:
            raise LLMError(
                f"no chat model available at {self.base_url} — load one in LM Studio "
                "(Developer tab) or set QANOUN_LLM_MODEL",
                kind="unreachable",
            )
        last_error: LLMError | None = None
        for candidate in candidates:
            body = {
                "model": candidate,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **self.extra,
            }
            try:
                data = self._request("POST", "/chat/completions", json=body)
                content = data["choices"][0]["message"]["content"] or ""
            except (LLMError, KeyError, IndexError) as exc:
                last_error = (
                    exc
                    if isinstance(exc, LLMError)
                    else LLMError(f"unexpected response shape: {str(exc)[:200]}")
                )
                if self.model:
                    raise  # explicit override: never silently fall back to another model
                continue  # auto-detect: try the next candidate
            self.model = candidate  # remember the winner for later calls
            return content
        raise LLMError(
            f"all {len(candidates)} candidate model(s) failed at {self.base_url}. "
            f"Load a chat model in LM Studio and retry. Last error: {last_error}",
            kind=last_error.kind if last_error else "error",
        )

    def chat_stream(
        self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 600
    ) -> Iterator[str]:
        """Yield answer tokens from an OpenAI-compatible SSE stream. Tries each candidate
        model until one accepts the request; once tokens flow, no retries."""
        candidates = self._candidate_models()
        if not candidates:
            raise LLMError(
                f"no chat model available at {self.base_url} — load one in LM Studio "
                "(Developer tab) or set QANOUN_LLM_MODEL",
                kind="unreachable",
            )
        last_error: LLMError | None = None
        for candidate in candidates:
            body = {
                "model": candidate,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **self.extra,
            }
            first_token = True
            try:
                with self.http.stream("POST", "/chat/completions", json=body) as response:
                    if response.status_code >= 400:
                        error_body = response.read().decode("utf-8", "replace")[:300]
                        raise LLMError(
                            f"model {candidate!r} → {response.status_code}: {error_body}",
                            kind=_kind_for(response.status_code),
                            status=response.status_code,
                        )
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            return
                        try:
                            chunk = json.loads(payload)
                            delta = chunk["choices"][0].get("delta", {})
                        except (ValueError, KeyError, IndexError):
                            continue
                        if token := delta.get("content"):
                            if first_token:
                                self.model = candidate  # winner: pin for later calls
                                first_token = False
                            yield token
                    return  # stream ended cleanly
            except httpx.HTTPError as exc:
                last_error = LLMError(
                    f"stream from {self.base_url} failed: {exc.__class__.__name__}",
                    kind="unreachable",
                )
                # Tokens already reached the caller: retrying another model would splice
                # two different answers together.
                if self.model or not first_token:
                    raise last_error from exc
                continue
            except LLMError as exc:
                last_error = exc
                if self.model:
                    raise
                continue
        raise LLMError(
            f"all {len(candidates)} candidate model(s) failed at {self.base_url}. "
            f"Load a chat model in LM Studio and retry. Last error: {last_error}",
            kind=last_error.kind if last_error else "error",
        )


def strip_reasoning(text: str) -> str:
    """Reasoning models served by LM Studio may prepend <think>...</think>."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
