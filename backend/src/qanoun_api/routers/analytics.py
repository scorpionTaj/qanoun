"""Analytics endpoints: corpus statistics for the data-science dashboard."""

from fastapi import APIRouter, Query

from qanoun_api.db import db
from qanoun_pipeline.normalize import STOPWORDS

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def summary():
    with db() as conn:
        totals = conn.execute(
            """
            SELECT (SELECT count(*) FROM laws), (SELECT count(*) FROM articles),
                   (SELECT count(*) FROM chunks), (SELECT count(DISTINCT domain) FROM laws),
                   (SELECT min(year) FROM laws), (SELECT max(year) FROM laws)
            """
        ).fetchone()
        by_domain = conn.execute(
            """
            SELECT l.domain, count(DISTINCT l.id), count(DISTINCT a.id),
                   (SELECT count(*) FROM chunks c WHERE c.law_id IN (SELECT id FROM laws l2 WHERE l2.domain = l.domain))
            FROM laws l LEFT JOIN articles a ON a.law_id = l.id
            GROUP BY l.domain ORDER BY count(DISTINCT l.id) DESC
            """
        ).fetchall()
        by_year = conn.execute(
            "SELECT year, count(*) FROM laws WHERE year IS NOT NULL GROUP BY year ORDER BY year"
        ).fetchall()
        by_language = conn.execute(
            "SELECT language, count(*) FROM laws GROUP BY language ORDER BY language"
        ).fetchall()
        article_lengths = conn.execute(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY length(text)), "
            "avg(length(text)), max(length(text)) FROM articles"
        ).fetchone()
    return {
        "totals": {
            "laws": totals[0], "articles": totals[1], "chunks": totals[2],
            "domains": totals[3], "year_min": totals[4], "year_max": totals[5],
        },
        "by_domain": [{"domain": r[0], "laws": r[1], "articles": r[2], "chunks": r[3]} for r in by_domain],
        "by_year": [{"year": r[0], "laws": r[1]} for r in by_year],
        "by_language": [{"language": r[0], "laws": r[1]} for r in by_language],
        "article_length": {"median_chars": article_lengths[0], "avg_chars": round(article_lengths[1]), "max_chars": article_lengths[2]},
    }


@router.get("/keywords")
def keywords(domain: str | None = Query(None), limit: int = Query(30, ge=5, le=100)):
    """Top tokens across article text — the dashboard's word-frequency panel.

    Postgres has no Arabic stemmer, so this is frequency over normalized tokens with the
    pipeline's stopword list applied afterwards; good enough for a corpus overview.
    """
    with db() as conn:
        rows = conn.execute(
            """
            SELECT word, count(*) AS n FROM (
                SELECT unnest(string_to_array(a.normalized, ' ')) AS word
                FROM articles a JOIN laws l ON l.id = a.law_id
                WHERE (%(domain)s::text IS NULL OR l.domain = %(domain)s)
                  AND length(a.normalized) > 0
            ) t
            WHERE word !~ '^[0-9]+$' AND length(word) > 1
            GROUP BY word ORDER BY n DESC LIMIT 300
            """,
            {"domain": domain},
        ).fetchall()
    filtered = [(w, n) for w, n in rows if w not in STOPWORDS and not w.isdigit()][:limit]
    return [{"token": w, "count": n} for w, n in filtered]
