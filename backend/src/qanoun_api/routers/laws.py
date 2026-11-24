"""Law catalog endpoints: browse, filter by domain, read a law article by article."""

from fastapi import APIRouter, HTTPException, Query

from qanoun_api.amendments import summarize
from qanoun_api.db import db

router = APIRouter(prefix="/api", tags=["laws"])

# Domain labels shipped once so the frontend keeps a single source of truth.
# Keys mirror qanoun_pipeline.catalog.DOMAINS.
_DOMAIN_LABELS: dict[str, dict[str, str]] = {
    "family": {"ar": "الأسرة", "fr": "Famille", "en": "Family"},
    "labour": {"ar": "الشغل", "fr": "Travail", "en": "Labour"},
    "civil": {"ar": "المدني", "fr": "Civil", "en": "Civil"},
    "housing": {"ar": "السكنى والكراء", "fr": "Logement & baux", "en": "Housing & leases"},
    "commercial": {"ar": "التجاري", "fr": "Commercial", "en": "Commercial"},
    "education": {"ar": "التعليم", "fr": "Éducation", "en": "Education"},
    "penal": {"ar": "الجنائي", "fr": "Pénal", "en": "Criminal"},
    "nationality": {"ar": "الجنسية", "fr": "Nationalité", "en": "Nationality"},
    "social": {"ar": "الاجتماعي", "fr": "Social", "en": "Social"},
    "justice": {"ar": "القضاء", "fr": "Justice", "en": "Justice"},
    "transport": {"ar": "النقل والسير", "fr": "Transport & circulation", "en": "Transport"},
    "property": {"ar": "العقاري", "fr": "Foncier", "en": "Property"},
    "governance": {"ar": "الحكامة والحقوق والحريات", "fr": "Gouvernance & libertés", "en": "Governance & freedoms"},
}


@router.get("/domains")
def list_domains():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT l.domain, count(DISTINCT l.id) AS laws, count(DISTINCT a.id) AS articles
            FROM laws l LEFT JOIN articles a ON a.law_id = l.id
            GROUP BY l.domain ORDER BY laws DESC, l.domain
            """
        ).fetchall()
    return [
        {
            "domain": r[0],
            "label": _DOMAIN_LABELS.get(r[0], {"ar": r[0], "fr": r[0], "en": r[0]}),
            "laws": r[1],
            "articles": r[2],
        }
        for r in rows
    ]


@router.get("/laws")
def list_laws(
    domain: str | None = Query(None),
    group: str | None = Query(None, alias="group"),
):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT l.slug, l.group_slug, l.title_ar, l.title_fr, l.law_number, l.year, l.domain,
                   l.language, l.source_url, l.page_count, l.article_count,
                   (SELECT count(*) FROM chunks c WHERE c.law_id = l.id) AS chunk_count,
                   l.parent_group
            FROM laws l
            WHERE (%(domain)s::text IS NULL OR l.domain = %(domain)s)
              AND (%(group)s::text IS NULL OR l.group_slug = %(group)s)
            ORDER BY l.domain, l.year NULLS LAST, l.slug
            """,
            {"domain": domain, "group": group},
        ).fetchall()
    return [
        {
            "slug": r[0], "group_slug": r[1], "title_ar": r[2], "title_fr": r[3],
            "law_number": r[4], "year": r[5], "domain": r[6], "language": r[7],
            "source_url": r[8], "page_count": r[9], "article_count": r[10],
            "chunk_count": r[11], "parent_group": r[12],
        }
        for r in rows
    ]


# Links whose target article exists now (they are stored as law slug + number, so a target
# law can be re-ingested without losing them). Source and target in the reading order.
_CITES_SQL = """
SELECT sa.number, r.target_law_slug, r.target_number
FROM article_refs r
JOIN articles sa ON sa.id = r.article_id
JOIN laws sl ON sl.id = sa.law_id
JOIN laws tl ON tl.slug = r.target_law_slug
JOIN articles ta ON ta.law_id = tl.id AND ta.number = r.target_number
WHERE sl.slug = %(slug)s {article_filter}
ORDER BY sa.ordinal, tl.slug <> sl.slug, ta.ordinal
"""

_CITED_BY_SQL = """
SELECT r.target_number, sl.slug, sa.number
FROM article_refs r
JOIN articles sa ON sa.id = r.article_id
JOIN laws sl ON sl.id = sa.law_id
JOIN laws tl ON tl.slug = r.target_law_slug
JOIN articles ta ON ta.law_id = tl.id AND ta.number = r.target_number
WHERE r.target_law_slug = %(slug)s {article_filter}
ORDER BY ta.ordinal, sl.slug <> r.target_law_slug, sl.slug, sa.ordinal
"""


def _law_titles(conn, slugs: set[str]) -> dict[str, dict]:
    if not slugs:
        return {}
    rows = conn.execute(
        "SELECT slug, title_ar, title_fr FROM laws WHERE slug = ANY(%(slugs)s)", {"slugs": list(slugs)}
    ).fetchall()
    return {row[0]: {"title_ar": row[1], "title_fr": row[2]} for row in rows}


def _references(conn, slug: str) -> dict:
    """Per article number: what it cites and what cites it (same law or another)."""
    cites: dict[str, list[dict]] = {}
    for number, law, target in conn.execute(_CITES_SQL.format(article_filter=""), {"slug": slug}).fetchall():
        cites.setdefault(number, []).append({"law_slug": law, "number": target})
    cited_by: dict[str, list[dict]] = {}
    for number, law, source in conn.execute(_CITED_BY_SQL.format(article_filter=""), {"slug": slug}).fetchall():
        cited_by.setdefault(number, []).append({"law_slug": law, "number": source})
    others = {ref["law_slug"] for refs in (*cites.values(), *cited_by.values()) for ref in refs} - {slug}
    return {"cites": cites, "cited_by": cited_by, "laws": _law_titles(conn, others)}


# A decree's parent: the edition of that law in the decree's language, else any edition.
# A law's decrees: every text whose parent is this law's group.
_FAMILY_SQL = """
SELECT 'parent' AS role, p.slug, p.title_ar, p.title_fr, p.law_number, p.year, p.language
FROM laws d JOIN LATERAL (
    SELECT * FROM laws p WHERE p.group_slug = d.parent_group
    ORDER BY p.language = d.language DESC, p.slug LIMIT 1
) p ON TRUE
WHERE d.slug = %(slug)s
UNION ALL
SELECT 'decree', d.slug, d.title_ar, d.title_fr, d.law_number, d.year, d.language
FROM laws l JOIN laws d ON d.parent_group = l.group_slug
WHERE l.slug = %(slug)s
ORDER BY 1, 6 NULLS LAST, 2
"""


def _decree_family(conn, slug: str) -> dict:
    parent, decrees = None, []
    for role, *fields in conn.execute(_FAMILY_SQL, {"slug": slug}).fetchall():
        item = dict(zip(("slug", "title_ar", "title_fr", "law_number", "year", "language"), fields, strict=True))
        if role == "parent":
            parent = item
        else:
            decrees.append(item)
    return {"parent": parent, "decrees": decrees}


@router.get("/laws/{slug}")
def law_detail(slug: str):
    with db() as conn:
        row = conn.execute(
            """
            SELECT slug, group_slug, title_ar, title_fr, law_number, year, domain, language,
                   source_url, page_count, article_count, preamble, warnings
            FROM laws WHERE slug = %(slug)s
            """,
            {"slug": slug},
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"unknown law: {slug}")
        articles = conn.execute(
            """
            SELECT a.id, a.number, a.ordinal, a.text, a.page_start, a.page_end
            FROM articles a JOIN laws l ON l.id = a.law_id
            WHERE l.slug = %(slug)s ORDER BY a.ordinal
            """,
            {"slug": slug},
        ).fetchall()
        references = _references(conn, slug)
        family = _decree_family(conn, slug)
    return {
        "slug": row[0], "group_slug": row[1], "title_ar": row[2], "title_fr": row[3],
        "law_number": row[4], "year": row[5], "domain": row[6], "language": row[7],
        "source_url": row[8], "page_count": row[9], "article_count": row[10],
        "preamble": row[11], "warnings": row[12],
        "amendments": summarize([row[11] or "", *(a[3] for a in articles)]),
        "references": references,
        **family,
        "articles": [
            {
                "id": a[0], "number": a[1], "ordinal": a[2], "text": a[3],
                "page_start": a[4], "page_end": a[5],
            }
            for a in articles
        ],
    }


@router.get("/laws/{slug}/articles/{number}")
def article_detail(slug: str, number: str):
    with db() as conn:
        row = conn.execute(
            """
            SELECT a.id, a.number, a.ordinal, a.text, a.page_start, a.page_end, l.slug, l.title_ar
            FROM articles a JOIN laws l ON l.id = a.law_id
            WHERE l.slug = %(slug)s AND a.number = %(number)s
            """,
            {"slug": slug, "number": number},
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"unknown article {slug}#{number}")
        params = {"slug": slug, "number": number}
        cites = [
            {"law_slug": law, "number": target}
            for _, law, target in conn.execute(
                _CITES_SQL.format(article_filter="AND sa.number = %(number)s"), params
            ).fetchall()
        ]
        cited_by = [
            {"law_slug": law, "number": source}
            for _, law, source in conn.execute(
                _CITED_BY_SQL.format(article_filter="AND r.target_number = %(number)s"), params
            ).fetchall()
        ]
        titles = _law_titles(conn, {ref["law_slug"] for ref in (*cites, *cited_by)} | {slug})
    for ref in (*cites, *cited_by):
        ref.update(titles.get(ref["law_slug"], {}))
    return {
        "id": row[0], "number": row[1], "ordinal": row[2], "text": row[3],
        "page_start": row[4], "page_end": row[5], "law_slug": row[6], "law_title": row[7],
        "cites": cites, "cited_by": cited_by,
    }
