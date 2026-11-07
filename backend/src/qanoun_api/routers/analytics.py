"""Analytics endpoints: corpus statistics for the data-science dashboard."""

import re

from fastapi import APIRouter, Query

from qanoun_api.db import db
from qanoun_pipeline.normalize import STOPWORDS

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Corpus-specific boilerplate: words that dominate legal prose without carrying domain
# meaning. The document-frequency cap (max_df) removes most of these automatically; this
# list catches the borderline ones and the OCR ligature artifacts (اال/اجل come from
# reversed lam-alef in the D.O.C.'s broken text layer).
# fmt: off
KEYWORD_BOILERPLATE = frozenset({
    # structural words: every law cites القانون رقم… and heads every المادة/الفصل
    "القانون", "القانوني", "القانونيه", "الماده", "الفصل", "الباب", "القسم", "الفقره",
    "الفقرات", "التماس", "التالي", "السابق", "السالف", "المشار", "الذكر", "اعلاه", "اعاله",
    "بمقتضي", "مقتضي", "المنصوص", "منصوص", "طبقا", "عملا", "تحمل", "نص", "نصا", "نصا",
    # modal / functional verbs
    "يمكن", "يجب", "تم", "يجوز", "يتعين", "تعتبر", "يعد", "كان", "تصبح", "قامت",
    "وتتميم", "تغيير", "تعديل", "المعدل", "المعدله",
    # bound pronouns and particles that survive normalization
    "عليها", "عليه", "منها", "منه", "به", "بها", "له", "لها", "هذا", "هذه", "ذلك", "تلك",
    "حاله", "خلال", "اال", "اجل", "ال", "اى", "ايضا", "حتي", "الا", "غير", "بعد", "قبل",
    # French legal scaffolding (accented + unaccented)
    "si", "ses", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "d'un", "d'une", "l'un", "l'une", "mais", "chez", "donc", "alors", "quand", "comme",
    "aussi", "tres", "très", "avoir", "aura", "etait", "était", "ete", "été", "soit",
    "soient", "doit", "doivent", "fait", "faite", "avec", "meme", "même", "memes", "mêmes",
    "loi", "lois", "sera", "seront", "etre", "être", "chapitre", "paragraphe", "dispositions",
    "disposition", "suivant", "suivante", "suivantes", "présente", "présent", "article",
    "alinéa", "alinea", "conformément", "conformement", "peut", "peuvent", "lors", "tant",
    "surtout", "autant", "tellement", "aucun", "aucune", "chaque",
})
# fmt: on

# A token is boilerplate when it appears in more than this share of the corpus documents.
MAX_DF_RATIO = 0.6
MIN_TOKEN_LEN = 3

# French elision: l'article, d'un, s'il… — the article body hides behind the clitic.
_ELISION = re.compile(r"^(?:[ldnjsmtcq]|qu|jusqu|lorsqu|puisqu)['’]", re.IGNORECASE)


def _clean_token(word: str) -> str:
    return _ELISION.sub("", word)


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
    """Top informative tokens across article text — the dashboard's word-frequency panel.

    Three NLP filters, in order:
    1. SQL: no pure digits, minimum length, and a document-frequency cap (max_df) — a word
       occurring in more than MAX_DF_RATIO of the matching laws is corpus boilerplate
       ("القانون", "المادة"…), the same idea as scikit-learn's max_df.
    2. Python: the shared stopword list plus legal-scaffolding terms that the cap lets
       through when they cluster in a few big codes.
    """
    with db() as conn:
        law_total = conn.execute(
            "SELECT count(*) FROM laws WHERE (%(domain)s::text IS NULL OR domain = %(domain)s)",
            {"domain": domain},
        ).fetchone()[0]
        if not law_total:
            return []
        # the cap must never drop below 1: single-law domains (transport) keep their tokens
        max_df = max(1, int(law_total * MAX_DF_RATIO))
        rows = conn.execute(
            """
            SELECT word, sum(n) AS total, count(DISTINCT law_id) AS df FROM (
                SELECT a.law_id, regexp_replace(w.word, '^[^\w]+|[^\w]+$', '', 'g') AS word, count(*) AS n
                FROM articles a
                JOIN laws l ON l.id = a.law_id
                CROSS JOIN LATERAL unnest(string_to_array(a.normalized, ' ')) AS w(word)
                WHERE (%(domain)s::text IS NULL OR l.domain = %(domain)s)
                  AND length(a.normalized) > 0
                GROUP BY a.law_id, regexp_replace(w.word, '^[^\w]+|[^\w]+$', '', 'g')
            ) t
            WHERE word !~ '^[0-9]+$' AND length(word) >= %(min_len)s
            GROUP BY word
            HAVING count(DISTINCT law_id) <= %(max_df)s
            ORDER BY total DESC
            LIMIT 400
            """,
            {"domain": domain, "min_len": MIN_TOKEN_LEN, "max_df": max_df},
        ).fetchall()
    # merge French elision variants (l'article / l'article with curly apostrophe), then filter
    merged: dict[str, int] = {}
    for w, n, _df in rows:
        token = _clean_token(w)
        merged[token] = merged.get(token, 0) + n
    filtered = [
        (w, n)
        for w, n in sorted(merged.items(), key=lambda kv: -kv[1])
        if len(w) >= MIN_TOKEN_LEN
        and w not in STOPWORDS
        and w not in KEYWORD_BOILERPLATE
        and not w.isdigit()
    ][:limit]
    return [{"token": w, "count": n} for w, n in filtered]
