"""Minimal client for any OpenAI-compatible chat endpoint: LM Studio, Ollama, vLLM,
OpenRouter or a custom gateway (ported from darija-rag).

    QANOUN_LLM_URL    base URL ending in /v1 (default: LM Studio, http://localhost:1234/v1)
    QANOUN_LLM_MODEL  model id; empty means auto-detect (see _candidate_models)
    QANOUN_LLM_KEY    bearer token, if the endpoint needs one

Model auto-detection builds an ordered candidate list — loaded models with a known chat
architecture first, then other loaded models, then the server's listed models — and tries
each until one answers. This survives LM Studio quirks like a non-chat model (e.g. a
speech model with arch=None) sitting loaded while the real LLMs are unloaded. Every error
carries the endpoint's response body, so "returned 400" always says WHY.
"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

from qanoun_api.config import SETTINGS

DEFAULT_URL = "http://localhost:1234/v1"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMClient:
    base_url: str = DEFAULT_URL
    model: str = ""  # explicit override from env; empty = auto-detect
    api_key: str = ""
    timeout: float = 120.0
    _http: httpx.Client | None = field(default=None, repr=False)

    @classmethod
    def from_settings(cls) -> "LLMClient":
        return cls(
            base_url=SETTINGS.llm_url,
            model=SETTINGS.llm_model,
            api_key=SETTINGS.llm_key,
        )

    @classmethod
    def from_env(cls) -> "LLMClient":  # convenience for scripts/tests
        return cls(
            base_url=os.environ.get("QANOUN_LLM_URL", DEFAULT_URL).rstrip("/"),
            model=os.environ.get("QANOUN_LLM_MODEL", ""),
            api_key=os.environ.get("QANOUN_LLM_KEY", ""),
        )

    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._http = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)
        return self._http

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise LLMError(
                f"LLM endpoint {self.base_url} is unreachable ({exc.__class__.__name__}). "
                "Start the LM Studio server (Developer tab) or set QANOUN_LLM_URL."
            ) from exc
        if response.status_code >= 400:
            raise LLMError(f"LLM endpoint returned {response.status_code}: {response.text[:300]}")
        return response.json()

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
                "(Developer tab) or set QANOUN_LLM_MODEL"
            )
        last_error: LLMError | None = None
        for candidate in candidates:
            body = {
                "model": candidate,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                data = self._request("POST", "/chat/completions", json=body)
                content = data["choices"][0]["message"]["content"] or ""
            except (LLMError, KeyError, IndexError) as exc:
                last_error = exc if isinstance(exc, LLMError) else LLMError(f"unexpected response shape: {str(exc)[:200]}")
                if self.model:
                    raise  # explicit override: never silently fall back to another model
                continue  # auto-detect: try the next candidate
            self.model = candidate  # remember the winner for later calls
            return content
        raise LLMError(
            f"all {len(candidates)} candidate model(s) failed at {self.base_url}. "
            f"Load a chat model in LM Studio and retry. Last error: {last_error}"
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
                "(Developer tab) or set QANOUN_LLM_MODEL"
            )
        last_error: LLMError | None = None
        for index, candidate in enumerate(candidates):
            body = {
                "model": candidate,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            try:
                with self.http.stream("POST", "/chat/completions", json=body) as response:
                    if response.status_code >= 400:
                        error_body = response.read().decode("utf-8", "replace")[:300]
                        raise LLMError(
                            f"model {candidate!r} → {response.status_code}: {error_body}"
                        )
                    first_token = True
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
                last_error = LLMError(f"stream from {self.base_url} failed: {exc.__class__.__name__}")
                if self.model:
                    raise
                continue
            except LLMError as exc:
                last_error = exc
                if self.model:
                    raise
                continue
        raise LLMError(
            f"all {len(candidates)} candidate model(s) failed at {self.base_url}. "
            f"Load a chat model in LM Studio and retry. Last error: {last_error}"
        )


def strip_reasoning(text: str) -> str:
    """Reasoning models served by LM Studio may prepend <think>...</think>."""
    import re

    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
