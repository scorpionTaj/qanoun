"""Amendments mentioned in a law's own text (editorial footnotes of the official PDFs).

The consolidated texts from adala.justice.gov.ma carry footnotes such as
  «تم تغيير وتتميم الفصل 179 أعلاه بموجب القانون رقم 72.03»
  «Article 9 modifié, complété et remplacé par la loi n° 72-03»
Ingestion keeps them inside the article text — often in the *next* article, since a
footnote sits at the bottom of the page — so each footnote is parsed for the article it
names, not where it happens to be stored. This lists what the text says; it is not a
point-in-time history.
"""

import re
from collections import defaultdict

_AR_NOTE = re.compile(r"تم\s*(?:تغيير|تتميم|نسخ|تعويض|تعديل)[^؛]{0,260}?رقم\s*(\d+\.\s?\d+(?:\.\s?\d+)?)")
_AR_TARGET = re.compile(r"(?:الفصل|المادة|الفصول|المواد)\s*(\d+(?:-\d+)?)")
_AR_BY = re.compile(r"(?:بموجب|بمقتضى)")

_FR_NOTE = re.compile(
    r"((?:Alinéa|Paragraphe|Intitulé|Article|Articles)[^.;]{0,60}?)"
    r"(?:modifié|complété|abrogé|remplacé|ajouté)[^;]{0,140}?"
    r"(?:loi|dahir(?: portant loi)?)\s*n[°o]\s*(\d+[-.]\s?\d+(?:[-.]\s?\d+)?)",
    re.IGNORECASE,
)
_FR_TARGET = re.compile(r"article\s+(\d+(?:-\d+)?|premier)", re.IGNORECASE)


def parse_amendments(text: str) -> list[tuple[str | None, str]]:
    """(amended article number or None, amending text's number) for each footnote."""
    found: list[tuple[str | None, str]] = []
    for note in _AR_NOTE.finditer(text):
        body = note.group(0)
        by = _AR_BY.search(body)
        if not by:  # «تم تغيير ...» without «بموجب/بمقتضى» is ordinary legal prose
            continue
        target = _AR_TARGET.search(body[: by.start()])
        found.append((target.group(1) if target else None, re.sub(r"\s", "", note.group(1))))
    for note in _FR_NOTE.finditer(text):
        target = _FR_TARGET.search(note.group(1))
        number = target.group(1) if target else None
        found.append(("1" if number and number.lower() == "premier" else number, re.sub(r"\s", "", note.group(2)).replace(".", "-")))
    return found


def summarize(texts: list[str]) -> dict:
    """Amending texts (most frequent first) and, per article, which texts changed it."""
    by_law: dict[str, set[str]] = defaultdict(set)
    mentions: dict[str, int] = defaultdict(int)
    by_article: dict[str, set[str]] = defaultdict(set)
    for text in texts:
        for article, ref in parse_amendments(text):
            mentions[ref] += 1
            if article:
                by_law[ref].add(article)
                by_article[article].add(ref)
    laws = [
        {"ref": ref, "mentions": n, "articles": sorted(by_law[ref], key=_article_key)}
        for ref, n in sorted(mentions.items(), key=lambda kv: -kv[1])
    ]
    return {"laws": laws, "articles": {a: sorted(refs) for a, refs in by_article.items()}}


def _article_key(number: str) -> tuple[int, ...]:
    return tuple(int(p) for p in number.split("-") if p.isdigit())
