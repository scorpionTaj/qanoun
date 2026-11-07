"""LLM client: model auto-detection with candidate fallback, error bodies surfaced."""

import httpx
import pytest

from qanoun_api.rag.llm import LLMClient, LLMError


def make_client(candidates: list[str], failing: set[str], reply: str = "مرحبا") -> LLMClient:
    """LLMClient backed by a MockTransport that 400s the models in `failing`."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url.path
        if url.endswith("/models") or url.endswith("/api/v0/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": m, "state": "loaded" if i == 0 else "not-loaded",
                                "type": "llm", "arch": None if i == 0 else "gemma4"}
                               for i, m in enumerate(candidates)]},
            )
        if url.endswith("/chat/completions"):
            body = request.read().decode()
            for m in failing:
                if m in body:
                    return httpx.Response(
                        400, json={"error": {"message": f"model {m} is broken", "type": "invalid_request_error"}}
                    )
            if '"stream": true' in body or '"stream":true' in body:
                sse = 'data: {"choices": [{"delta": {"content": "مرحبا"}}]}\n\ndata: [DONE]\n\n'
                return httpx.Response(200, text=sse)
            return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})
        return httpx.Response(404)

    client = LLMClient(base_url="http://fake/v1")
    client._http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake/v1")
    return client


def test_chat_falls_back_to_first_working_model():
    # candidate #0 is loaded but broken (the phonon case); #1 works
    client = make_client(["phonon-40m", "gemma-4-12b"], failing={"phonon-40m"})
    assert client.chat([{"role": "user", "content": "hi"}]) == "مرحبا"
    assert client.model == "gemma-4-12b"  # winner pinned


def test_chat_error_includes_response_body():
    client = make_client(["broken-model"], failing={"broken-model"})
    with pytest.raises(LLMError, match="model broken-model is broken"):
        client.chat([{"role": "user", "content": "hi"}])


def test_explicit_model_override_never_falls_back():
    client = make_client(["phonon-40m", "gemma-4-12b"], failing={"gemma-4-12b"})
    client.model = "gemma-4-12b"
    with pytest.raises(LLMError, match="gemma-4-12b is broken"):
        client.chat([{"role": "user", "content": "hi"}])


def test_stream_falls_back_and_pins_winner():
    client = make_client(["phonon-40m", "gemma-4-12b"], failing={"phonon-40m"})
    tokens = list(client.chat_stream([{"role": "user", "content": "hi"}]))
    assert tokens == ["مرحبا"]  # mock returns full content as one delta
    assert client.model == "gemma-4-12b"


def test_all_candidates_failing_lists_them():
    client = make_client(["a-model", "b-model"], failing={"a-model", "b-model"})
    with pytest.raises(LLMError, match="all 2 candidate model"):
        client.chat([{"role": "user", "content": "hi"}])
