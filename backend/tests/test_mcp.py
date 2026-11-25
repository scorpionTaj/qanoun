"""The MCP endpoint (/mcp): JSON-RPC over streamable HTTP, through the real app and lifespan."""

from contextlib import contextmanager

import pytest
from conftest import make_hit
from fastapi.testclient import TestClient

from qanoun_api import main, mcp_server
from qanoun_api.config import SETTINGS
from qanoun_api.rag.retrieval import RetrievalResult

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def client():
    """A fresh app lifespan per test, without a database. Starting the app many times in one
    process is itself under test: the SDK's session manager runs only once per instance."""

    @contextmanager
    def no_db():
        yield None

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(main, "db", no_db)
        patch.setattr(main, "ensure_schema", lambda conn: [])
        patch.setattr(main, "_warm_up", lambda: None)
        with TestClient(main.app) as client:
            yield client


@pytest.fixture
def mcp(client):
    calls = iter(range(1, 100))

    def rpc(method: str, params: dict | None = None) -> dict:
        body = {"jsonrpc": "2.0", "id": next(calls), "method": method, "params": params or {}}
        response = client.post("/mcp", json=body, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/json")
        return response.json()

    return rpc


def _call(rpc, tool: str, **arguments) -> dict:
    result = rpc("tools/call", {"name": tool, "arguments": arguments})["result"]
    return result


def test_initialize_and_list_tools(mcp):
    init = mcp("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "0"}})["result"]
    assert init["serverInfo"]["name"] == "qanoun"
    assert "cite the law and article" in init["instructions"]
    tools = {t["name"]: t for t in mcp("tools/list")["result"]["tools"]}
    assert set(tools) == {"search_laws", "get_article", "list_laws"}
    assert all(t["annotations"]["readOnlyHint"] for t in tools.values())
    assert tools["search_laws"]["inputSchema"]["required"] == ["query"]
    # the search does not translate: the agent is told to rewrite Darija/Arabizi into MSA
    assert "Rewrite Darija" in tools["search_laws"]["description"]


def test_search_laws_returns_articles_with_links(mcp, monkeypatch):
    seen = {}

    def search(query, k, domain, law_slug):
        seen.update(query=query, k=k, domain=domain, law_slug=law_slug)
        return RetrievalResult(query=query, search_query="سن الزواج", hits=[make_hit(number="19")])

    monkeypatch.setattr(mcp_server.retrieval, "search", search)
    monkeypatch.setattr(mcp_server, "SETTINGS", type(SETTINGS)(web_url="https://qanoun.example"))
    result = _call(mcp, "search_laws", query="ch7al l3mr dyal zwaj", domain="family", k=99)
    data = result["structuredContent"]
    assert seen == {"query": "ch7al l3mr dyal zwaj", "k": 20, "domain": "family", "law_slug": None}  # k capped
    assert data["searched_for"] == "سن الزواج"
    assert data["results"][0]["law"] == "family-code-ar" and data["results"][0]["article"] == "19"
    assert data["results"][0]["link"] == "https://qanoun.example/ar/laws/family-code-ar#article-19"


def test_get_article_with_references(mcp, fake_db):
    fake_db({
        "WHERE sl.slug": [("12", "civil-procedure-ar", "38")],
        "WHERE r.target_law_slug": [("12", "family-code-ar", "16")],
        "slug = ANY": [("civil-procedure-ar", "المسطرة المدنية", "Code de procédure civile"),
                       ("family-code-ar", "مدونة الأسرة", "Code de la famille")],
        "JOIN laws l ON": [(1, "12", 12, "يتم الزواج بعقد.", 30, 31, "family-code-ar", "مدونة الأسرة")],
    })
    data = _call(mcp, "get_article", law="family-code-ar", article="12")["structuredContent"]
    assert data["text"] == "يتم الزواج بعقد." and data["pages"] == [30, 31]
    assert data["cites"] == [{"law": "civil-procedure-ar", "article": "38", "law_title": "المسطرة المدنية"}]
    assert data["cited_by"][0]["article"] == "16"
    assert data["link"] is None  # no web address configured


def test_unknown_article_is_a_tool_error(mcp, fake_db):
    fake_db({"JOIN laws l ON": []})
    result = _call(mcp, "get_article", law="family-code-ar", article="9999")
    assert result["isError"] is True
    assert "unknown article family-code-ar#9999" in result["content"][0]["text"]


def test_list_laws(mcp, fake_db):
    fake_db({"FROM laws l": [("minimum-wage-decree-ar", "minimum-wage-decree", "مرسوم الحد الأدنى للأجر", None,
                              "2.24.1122", 2024, "labour", "ar", None, 3, 4, 5, "labour-code")]})
    data = _call(mcp, "list_laws", domain="labour")["structuredContent"]["result"]
    assert data == [{"slug": "minimum-wage-decree-ar", "title_ar": "مرسوم الحد الأدنى للأجر", "title_fr": None,
                     "number": "2.24.1122", "year": 2024, "domain": "labour", "language": "ar",
                     "articles": 4, "implements": "labour-code"}]


def test_endpoint_is_closed_outside_the_lifespan():
    with pytest.raises(RuntimeError, match="lifespan"):
        TestClient(main.app).post("/mcp", json={}, headers=HEADERS)


def test_get_is_refused_at_once(client):
    # stateless: no server-to-client stream; a GET must not hang until the function times out
    assert client.get("/mcp", headers={"Accept": "text/event-stream"}).status_code == 405
