"""Laws + analytics endpoints against a faked DB connection."""

from fastapi.testclient import TestClient

from qanoun_api.main import app

client = TestClient(app)

LAW_ROW = (
    "family-code-ar", "moudawana", "مدونة الأسرة", "Code de la famille", "70-03", 2004,
    "family", "ar", "https://example.org/x.pdf", 107, 400, 417,
)
DOMAIN_ROW = ("family", 2, 800)
DETAIL_ROW = (
    "family-code-ar", "moudawana", "مدونة الأسرة", "Code de la famille", "70-03", 2004,
    "family", "ar", "https://example.org/x.pdf", 107, 400, "بسم الله", [],
)
ARTICLE_ROW = (1, "12", 12, "يتم الزواج بعقد.", 30, 30)


def test_list_laws(fake_db):
    conn = fake_db({"FROM laws l": [LAW_ROW]})
    response = client.get("/api/laws", params={"domain": "family"})
    assert response.status_code == 200
    laws = response.json()
    assert laws[0]["slug"] == "family-code-ar"
    assert laws[0]["article_count"] == 400
    assert laws[0]["chunk_count"] == 417
    assert any("FROM laws l" in q for q in conn.queries)


def test_list_domains(fake_db):
    fake_db({"GROUP BY l.domain": [DOMAIN_ROW]})
    response = client.get("/api/domains")
    domains = response.json()
    assert domains[0]["domain"] == "family"
    assert domains[0]["label"]["ar"] == "الأسرة"


def test_law_detail_includes_articles(fake_db):
    fake_db({"FROM laws WHERE slug": [DETAIL_ROW], "JOIN laws l ON": [ARTICLE_ROW]})
    response = client.get("/api/laws/family-code-ar")
    assert response.status_code == 200
    data = response.json()
    assert data["preamble"].startswith("بسم")
    assert data["articles"][0]["number"] == "12"


def test_unknown_law_is_404(fake_db):
    fake_db({"FROM laws WHERE slug": []})
    assert client.get("/api/laws/nope").status_code == 404


def test_article_detail(fake_db):
    fake_db({"JOIN laws l ON": [(1, "12", 12, "نص", 30, 30, "family-code-ar", "مدونة الأسرة")]})
    response = client.get("/api/laws/family-code-ar/articles/12")
    assert response.status_code == 200
    assert response.json()["law_slug"] == "family-code-ar"


def test_analytics_summary_shape(fake_db):
    fake_db({
        "SELECT (SELECT count(*) FROM laws)": [(1, 400, 417, 1, 2004, 2004)],
        "GROUP BY l.domain ORDER BY count": [("family", 1, 400, 417)],
        "GROUP BY year ORDER BY year": [(2004, 1)],
        "GROUP BY language ORDER BY language": [("ar", 1)],
        "percentile_cont": [(250.0, 300.5, 900)],
    })
    response = client.get("/api/analytics/summary")
    data = response.json()
    assert data["totals"]["laws"] == 1
    assert data["by_domain"][0]["domain"] == "family"
    assert data["article_length"]["max_chars"] == 900


def test_analytics_keywords_filter_stopwords(fake_db):
    # (word, total, df) — القانون/si/ال are boilerplate or too short; الزواج/صداق survive
    fake_db({
        "FROM laws WHERE": [(4,)],
        "GROUP BY word": [
            ("القانون", 3831, 4), ("si", 94, 2), ("ال", 90, 3), ("الزواج", 120, 2),
            ("صداق", 60, 1), ("123", 90, 1),
        ],
    })
    tokens = client.get("/api/analytics/keywords").json()
    words = [t["token"] for t in tokens]
    assert "القانون" not in words  # boilerplate
    assert "si" not in words  # French stopword
    assert "ال" not in words  # OCR particle (also below min length)
    assert "123" not in words  # pure digits
    assert words[0] == "الزواج"
    assert "صداق" in words


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_root_serves_swagger_ui_and_docs_redirects_there():
    page = client.get("/")
    assert page.status_code == 200 and "swagger-ui" in page.text
    assert "/openapi.json" in page.text
    moved = client.get("/docs", follow_redirects=False)
    assert moved.status_code == 307 and moved.headers["location"] == "/"
    schema = client.get("/openapi.json").json()
    assert "/api/chat" in schema["paths"] and "/" not in schema["paths"]
