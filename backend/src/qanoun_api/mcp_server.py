"""MCP server: lets AI agents (Claude, Cursor, …) search and read Moroccan law.

Served by the API at /mcp (streamable HTTP, stateless, JSON responses, so it runs on a
serverless function). Connect with:

    claude mcp add --transport http qanoun https://<api-host>/mcp

The tools reuse the REST handlers, so both surfaces return the same data. There is no `ask`
tool: the calling agent is itself a language model and composes the answer from the articles,
which keeps the server free of LLM costs.
"""

from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from qanoun_api import __version__
from qanoun_api.config import SETTINGS
from qanoun_api.rag import retrieval
from qanoun_api.routers import laws

server = MCPServer(
    name="qanoun",
    title="Qanoun: Moroccan law",
    version=__version__,
    instructions=(
        "Official Moroccan legal texts (codes, laws, implementing decrees) in Arabic and French, "
        "split into articles. Use search_laws to find the articles that answer a question; search "
        "in Modern Standard Arabic or French (rewrite a Darija or Arabizi question into MSA "
        "first: the texts are written in MSA), get_article to read one in full with the articles "
        "it cites and that cite it, and list_laws to see what the corpus covers. Base answers on "
        "the returned text and cite the law and article number; say so when nothing relevant is "
        "found rather than answering from memory. This is legal information, not legal advice."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


# Return types: they become each tool's output schema, so agents know the fields.
class Passage(TypedDict):
    law: str
    law_title: str
    law_title_fr: str | None
    article: str | None
    page: int | None
    text: str
    link: str | None


class SearchResult(TypedDict):
    searched_for: str  # the query actually searched
    results: list[Passage]


class Ref(TypedDict):
    law: str
    article: str
    law_title: str | None


class Article(TypedDict):
    law: str
    law_title: str
    article: str
    pages: list[int | None]
    text: str
    cites: list[Ref]
    cited_by: list[Ref]
    link: str | None


class Law(TypedDict):
    slug: str
    title_ar: str
    title_fr: str | None
    number: str | None
    year: int | None
    domain: str
    language: str
    articles: int | None
    implements: str | None  # group of the law an implementing decree applies


def _link(slug: str, number: str | None = None) -> str | None:
    """Deep link into the web reader, when the deployment says where it is."""
    if not SETTINGS.web_url:
        return None
    locale = "fr" if slug.endswith("-fr") else "ar"
    anchor = f"#article-{number}" if number else ""
    return f"{SETTINGS.web_url}/{locale}/laws/{slug}{anchor}"


@server.tool(annotations=READ_ONLY)
def search_laws(query: str, domain: str | None = None, law: str | None = None, k: int = 8) -> SearchResult:
    """Search Moroccan legal texts; return the best-matching articles with their text.

    Args:
        query: the question or keywords in Modern Standard Arabic or French. Rewrite Darija
            or Arabizi into MSA first («ch7al l3mr bach tzwj» → «ما هو السن القانوني للزواج»):
            the texts are in MSA, and this search does not translate.
        domain: restrict to one domain (see list_laws), e.g. "family", "labour", "criminal".
        law: restrict to one law by its slug (see list_laws), e.g. "labour-code-ar".
        k: number of articles to return (1-20).
    """
    result = retrieval.search(query[:500], k=max(1, min(k, 20)), domain=domain, law_slug=law)
    return {
        "searched_for": result.search_query,
        "results": [
            {
                "law": hit.law_slug, "law_title": hit.law_title, "law_title_fr": hit.law_title_fr,
                "article": hit.article_number, "page": hit.page, "text": hit.text,
                "link": _link(hit.law_slug, hit.article_number),
            }
            for hit in result.hits
        ],
    }


@server.tool(annotations=READ_ONLY)
def get_article(law: str, article: str) -> Article:
    """Read one article in full, with the articles it cites and the articles that cite it.

    Args:
        law: the law's slug, e.g. "family-code-ar" (from search_laws or list_laws).
        article: the article number as printed, e.g. "19", "65-1", "4-bis".
    """
    try:
        data = laws.article_detail(law, article)
    except HTTPException as exc:
        raise ToolError(exc.detail) from None  # its message reaches the agent
    refs = lambda items: [
        {"law": r["law_slug"], "article": r["number"], "law_title": r.get("title_ar")} for r in items
    ]
    return {
        "law": data["law_slug"], "law_title": data["law_title"], "article": data["number"],
        "pages": [data["page_start"], data["page_end"]], "text": data["text"],
        "cites": refs(data["cites"]), "cited_by": refs(data["cited_by"]),
        "link": _link(law, article),
    }


@server.tool(annotations=READ_ONLY)
def list_laws(domain: str | None = None) -> list[Law]:
    """List the laws and implementing decrees in the corpus (slug, titles, number, year, domain).

    Args:
        domain: only this domain, e.g. "family", "labour", "commercial".
    """
    return [
        {
            "slug": r["slug"], "title_ar": r["title_ar"], "title_fr": r["title_fr"],
            "number": r["law_number"], "year": r["year"], "domain": r["domain"],
            "language": r["language"], "articles": r["article_count"],
            "implements": r["parent_group"],
        }
        for r in laws.list_laws(domain=domain, group=None)
    ]


class _Endpoint:
    """The ASGI app main.py routes /mcp to. It forwards to the transport of the running app
    lifespan: the SDK's session manager runs once per instance, and an app can be started more
    than once in one process (tests, reloads), so each start builds its own (see `running`)."""

    transport = None

    async def __call__(self, scope, receive, send):
        if self.transport is None:
            raise RuntimeError("the MCP endpoint is served only while the app's lifespan runs")
        await self.transport(scope, receive, send)


endpoint = _Endpoint()


@asynccontextmanager
async def running():
    """Start the MCP transport for one app lifespan.

    Stateless with JSON responses: no session survives between requests, which a serverless
    function could not keep anyway. No DNS-rebinding host check: the server is public and
    read-only, and it reads no cookie or credential."""
    app = server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True,
                                     host="0.0.0.0")
    endpoint.transport = app.routes[0].endpoint
    try:
        async with server.session_manager.run():
            yield
    finally:
        endpoint.transport = None
