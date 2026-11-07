"""Law catalog endpoints: browse, filter by domain, read a law article by article."""

from fastapi import APIRouter, HTTPException, Query

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
                   (SELECT count(*) FROM chunks c WHERE c.law_id = l.id) AS chunk_count
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
            "chunk_count": r[11],
        }
        for r in rows
    ]


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
    return {
        "slug": row[0], "group_slug": row[1], "title_ar": row[2], "title_fr": row[3],
        "law_number": row[4], "year": row[5], "domain": row[6], "language": row[7],
        "source_url": row[8], "page_count": row[9], "article_count": row[10],
        "preamble": row[11], "warnings": row[12],
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
    return {
        "id": row[0], "number": row[1], "ordinal": row[2], "text": row[3],
        "page_start": row[4], "page_end": row[5], "law_slug": row[6], "law_title": row[7],
    }
