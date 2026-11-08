"""Provider registry: .env parsing, model recommendation, fallback between providers."""

import pytest

from qanoun_api.rag.llm import LLMError
from qanoun_api.rag.providers import LLMRouter, load_providers, recommend_model


def test_cloud_key_becomes_default_and_local_stays_available():
    providers = load_providers({"QANOUN_GEMINI_KEY": "k"})
    assert next(p.id for p in providers) == "gemini"
    configured = [p.id for p in providers if p.configured]
    assert configured == ["gemini", "local"]


def test_explicit_preference_wins_and_unkeyed_preference_is_ignored():
    env = {"QANOUN_GEMINI_KEY": "k", "QANOUN_LLM_PROVIDER": "local"}
    assert load_providers(env)[0].id == "local"
    env = {"QANOUN_LLM_PROVIDER": "nvidia"}  # no NVIDIA key → falls back to local
    assert load_providers(env)[0].id == "local"


def test_recommend_gemini_picks_newest_stable_flash_lite():
    ids = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite",
           "gemini-3.0-flash-preview", "gemini-2.5-pro", "text-embedding-004",
           "gemini-2.5-flash-preview-tts"]
    assert recommend_model("gemini", ids) == "gemini-2.5-flash-lite"


def test_recommend_openrouter_prefers_free_known_family():
    ids = ["openai/gpt-5", "meta-llama/llama-3.3-70b-instruct:free", "acme/tiny:free"]
    assert recommend_model("openrouter", ids) == "meta-llama/llama-3.3-70b-instruct:free"


def test_recommend_skips_non_chat_models():
    assert recommend_model("nvidia", ["nvidia/nv-embedqa-e5-v5"]) is None


class FakeClient:
    def __init__(self, tokens=None, error=None, mid_error=False):
        self.tokens, self.error, self.mid_error, self.model = tokens or [], error, mid_error, ""

    def chat_stream(self, messages, **kw):
        if self.error and not self.mid_error:
            raise self.error
        yield from self.tokens
        if self.mid_error:
            raise self.error

    def chat(self, messages, **kw):
        if self.error:
            raise self.error
        return "".join(self.tokens)


def router_with(clients: dict) -> LLMRouter:
    router = LLMRouter(load_providers({"QANOUN_GEMINI_KEY": "k", "QANOUN_LLM_MODEL": "m"}))
    router.resolve_model = lambda provider, model="": model or "auto"  # no network
    router.models = lambda pid: ["auto"]
    router._client = lambda provider, model: clients[provider.id]
    return router


def test_falls_back_to_next_provider_and_reports_who_answered():
    router = router_with({
        "gemini": FakeClient(error=LLMError("429", kind="rate_limit")),
        "local": FakeClient(tokens=["مرحبا"]),
    })
    started = []
    out = list(router.chat_stream([], on_start=lambda p, m: started.append(p.id)))
    assert out == ["مرحبا"] and started == ["local"]


def test_all_providers_failing_reports_most_actionable_kind():
    router = router_with({
        "gemini": FakeClient(error=LLMError("bad key", kind="auth")),
        "local": FakeClient(error=LLMError("refused", kind="unreachable")),
    })
    with pytest.raises(LLMError) as info:
        list(router.chat_stream([]))
    assert info.value.kind == "auth"
    assert "bad key" in str(info.value) and "refused" in str(info.value)


def test_mid_answer_failure_is_not_spliced_with_another_provider():
    router = router_with({
        "gemini": FakeClient(tokens=["half"], error=LLMError("reset", kind="unreachable"),
                             mid_error=True),
        "local": FakeClient(tokens=["other"]),
    })
    out = []
    with pytest.raises(LLMError):
        for token in router.chat_stream([]):
            out.append(token)  # noqa: PERF402 — keep tokens seen before the raise
    assert out == ["half"]


def test_requesting_unkeyed_provider_is_a_clear_error():
    router = LLMRouter(load_providers({}))
    with pytest.raises(LLMError, match="QANOUN_GEMINI_KEY"):
        router.get("gemini")


def test_busy_model_falls_back_to_sibling_model_of_same_provider():
    router = LLMRouter(load_providers({"QANOUN_GEMINI_KEY": "k"}))
    router.models = lambda pid: ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
    clients = {
        "gemini-3.8-flash": FakeClient(error=LLMError("503 high demand", kind="unavailable")),
        "gemini-2.5-flash": FakeClient(tokens=["جواب"]),
    }
    router._client = lambda provider, model: clients[model]
    used = []
    out = list(router.chat_stream([], on_start=lambda p, m: used.append(m)))
    assert out == ["جواب"] and used == ["gemini-2.5-flash"]


def test_ranked_models_skips_non_chat_and_orders_best_first():
    from qanoun_api.rag.providers import ranked_models

    ids = ["deep-research-pro-preview-12-2025", "gemini-2.5-flash", "gemini-3.8-flash",
           "gemini-2.5-flash-native-audio-latest", "gemini-2.5-pro", "gemini-3-flash-preview"]
    assert ranked_models("gemini", ids)[:2] == ["gemini-3.8-flash", "gemini-2.5-flash"]


def test_busy_model_is_tried_last_on_the_next_call():
    router = LLMRouter(load_providers({"QANOUN_GEMINI_KEY": "k"}))
    router.models = lambda pid: ["gemini-3.8-flash", "gemini-2.5-flash"]
    busy = FakeClient(error=LLMError("503", kind="unavailable"))
    ok = FakeClient(tokens=["x"])
    calls = []

    def client(provider, model):
        calls.append(model)
        return {"gemini-3.8-flash": busy, "gemini-2.5-flash": ok}[model]

    router._client = client
    list(router.chat_stream([]))
    calls.clear()
    list(router.chat_stream([]))
    assert calls == ["gemini-2.5-flash"]  # the busy model is no longer tried first


def test_gemini_requests_low_reasoning_effort():
    router = LLMRouter(load_providers({"QANOUN_GEMINI_KEY": "k"}))
    gemini = router.get("gemini")
    assert router._client(gemini, "m").extra == {"reasoning_effort": "low"}
    assert router._client(router.get("local"), "").extra == {}


NVIDIA_LIVE = [  # excerpt of the list an actual account returned (2026-11)
    "deepseek-ai/deepseek-coder-6.7b-instruct", "ibm/granite-34b-code-instruct",
    "deepseek-ai/deepseek-v4.1-flash", "google/codegemma-7b", "google/gemma-3-12b-it",
    "google/gemma-4-31b-it", "meta/llama-3.2-90b-vision-instruct", "meta/llama-guard-4-12b",
    "mistralai/mistral-large-2-instruct", "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nv-embedqa-mistral-7b-v2", "openai/gpt-oss-20b",
]


def test_nvidia_prefers_fast_multilingual_chat_models_not_code_models():
    from qanoun_api.rag.providers import ranked_models

    assert ranked_models("nvidia", NVIDIA_LIVE) == [
        "google/gemma-4-31b-it", "google/gemma-3-12b-it",
        "deepseek-ai/deepseek-v4.1-flash", "mistralai/mistral-large-2-instruct",
    ]


def test_gemini_interleaves_lite_and_flash_across_generations():
    from qanoun_api.rag.providers import ranked_models

    ids = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite",
           "gemini-3.1-flash-lite-preview", "gemini-3.8-flash-tts", "gemini-2.5-flash"]
    assert ranked_models("gemini", ids) == [
        "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-2.5-flash",
    ]


def test_connection_test_walks_candidates_and_remembers_failures():
    router = LLMRouter(load_providers({"QANOUN_NVIDIA_KEY": "k"}))
    router.models = lambda pid: ["deepseek-ai/deepseek-v4.1-flash", "google/gemma-4-31b-it"]
    clients = {
        "deepseek-ai/deepseek-v4.1-flash": FakeClient(error=LLMError("404 Function not found", kind="model")),
        "google/gemma-4-31b-it": FakeClient(tokens=["OK"]),
    }
    router._client = lambda provider, model: clients[model]
    result = router.test("nvidia")
    assert result["ok"] and result["model"] == "google/gemma-4-31b-it"
    assert result["failed"][0]["code"] == "model"
    # the 404 model now goes last for chat too
    assert next(m for _, m in router._chain("nvidia", "")) == "google/gemma-4-31b-it"


def test_router_rebuilds_when_env_file_changes(tmp_path, monkeypatch):
    import os

    from qanoun_api.rag import providers

    env = tmp_path / ".env"
    env.write_text("QANOUN_LLM_URL=http://localhost:1234/v1\n")
    monkeypatch.setattr(providers, "ENV_FILE", env)
    providers.set_router(None)
    assert not providers.get_router().get("local").api_key
    assert [p.id for p in providers.get_router().configured()] == ["local"]

    env.write_text('QANOUN_GEMINI_KEY="new-key"  \n# comment\nexport QANOUN_LLM_PROVIDER=gemini\n')
    os.utime(env, (env.stat().st_atime, env.stat().st_mtime + 5))
    router = providers.get_router()
    assert router.default.id == "gemini" and router.get("gemini").api_key == "new-key"
    providers.set_router(None)


def test_explicit_provider_never_falls_back_to_another_provider():
    router = router_with({
        "gemini": FakeClient(tokens=["from gemini"]),
        "local": FakeClient(error=LLMError("refused", kind="unreachable")),
    })
    with pytest.raises(LLMError, match="refused"):
        list(router.chat_stream([], provider_id="local"))


def test_explicit_model_is_the_only_attempt():
    router = LLMRouter(load_providers({"QANOUN_NVIDIA_KEY": "k"}))
    router.models = lambda pid: ["google/gemma-4-31b-it", "deepseek-ai/deepseek-v4.1-flash"]
    assert [m for _, m in router._chain("nvidia", "deepseek-ai/deepseek-v4.1-flash")] == [
        "deepseek-ai/deepseek-v4.1-flash"
    ]
    assert [m for _, m in router._chain("nvidia", "")] == [
        "google/gemma-4-31b-it", "deepseek-ai/deepseek-v4.1-flash"
    ]


def test_cloud_timeout_is_skipped_on_the_next_automatic_call():
    router = LLMRouter(load_providers({"QANOUN_GEMINI_KEY": "k"}))
    router.models = lambda pid: ["slow", "fast"]
    calls = []
    clients = {"slow": FakeClient(error=LLMError("ReadTimeout", kind="unreachable")),
               "fast": FakeClient(tokens=["ok"])}

    def client(provider, model):
        calls.append(model)
        return clients[model]

    router._client = client
    list(router.chat_stream([]))
    calls.clear()
    list(router.chat_stream([]))
    assert calls[0] == "fast"
