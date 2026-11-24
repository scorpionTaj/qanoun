"""Amendments mentioned in a law's own text (editorial footnotes of the official PDFs).

The consolidated texts from adala.justice.gov.ma carry footnotes such as
  «تم تغيير وتتميم الفصل 179 أعلاه بموجب القانون رقم 72.03»
  «Article 9 modifié, complété et remplacé par la loi n° 72-03»
Ingestion keeps them inside the article text — often in the *next* article, since a
footnote sits at the bottom of the page — so each footnote is parsed for the article it
names, not where it happens to be stored.

Each footnote gives the kind of change (amended, supplemented, repealed, replaced, added) and
a year: the year in the amending text's number («12.18» → 2018, dahir «1.11.151» → 2011),
which is when the bill was numbered (its promulgation can be a year later). A date written in
the note is used only when the number has none: notes go on to cite the *amended* law and its
own dahir, whose date would otherwise be taken for the amendment's. This is the history the text records, not the past
wording: the portal publishes only the current consolidated version.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

_AR_KINDS = {"تغيير": "amended", "تعديل": "amended", "تتميم": "supplemented", "نسخ": "repealed",
             "تعويض": "replaced", "إضافة": "added"}
_FR_KINDS = {"modifi": "amended", "complét": "supplemented", "abrog": "repealed", "remplac": "replaced",
             "ajout": "added"}
_YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")


@dataclass(frozen=True)
class Event:
    article: str | None  # the amended article, when the note names one
    ref: str  # the amending text's number, as printed («72.03», «72-03», «1-93-206»)
    kinds: tuple[str, ...]  # amended, supplemented, repealed, replaced, added
    year: int | None


def ref_year(ref: str) -> int | None:
    """Year in a Moroccan law or dahir number: «12.18» → 2018, «1-93-206» → 1993."""
    parts = re.split(r"[.\-]", ref)
    # law NN.YY, dahir 1.YY.NNN, decree 2.YY.NNN: the year is always the second part
    if not (len(parts) == 2 or (len(parts) == 3 and parts[0] in ("1", "2"))):
        return None
    yy = parts[1]
    if not (yy.isdigit() and len(yy) == 2):
        return None
    return 2000 + int(yy) if int(yy) <= 40 else 1900 + int(yy)

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


def parse_events(text: str) -> list[Event]:
    """One event per amendment footnote in text."""
    found: list[Event] = []
    for note in _AR_NOTE.finditer(text):
        body = note.group(0)
        by = _AR_BY.search(body)
        if not by:  # «تم تغيير ...» without «بموجب/بمقتضى» is ordinary legal prose
            continue
        target = _AR_TARGET.search(body[: by.start()])
        ref = re.sub(r"\s", "", note.group(1))
        kinds = tuple(dict.fromkeys(k for word, k in _AR_KINDS.items() if word in body[: by.start()]))
        citation = body[by.start():] + _rest_of_note(text, note.end())
        found.append(Event(target.group(1) if target else None, ref, kinds, _event_year(citation, ref)))
    for note in _FR_NOTE.finditer(text):
        target = _FR_TARGET.search(note.group(1))
        number = target.group(1) if target else None
        ref = re.sub(r"\s", "", note.group(2)).replace(".", "-")
        lowered = note.group(0).lower()
        kinds = tuple(dict.fromkeys(k for stem, k in _FR_KINDS.items() if stem in lowered))
        article = "1" if number and number.lower() == "premier" else number
        citation = note.group(0)[len(note.group(1)):] + _rest_of_note(text, note.end())
        found.append(Event(article, ref, kinds, _event_year(citation, ref)))
    return found


def _rest_of_note(text: str, end: int) -> str:
    """What follows the amending text's number in the same footnote (its date, if any)."""
    tail = text[end : end + 160]
    stop = re.search(r"[؛;]|تم\s|\b(?:Article|Alinéa)\b", tail)
    return tail[: stop.start()] if stop else tail


def _event_year(citation: str, ref: str) -> int | None:
    """The year in the law's number; a year written in the citation only as a fallback."""
    if (year := ref_year(ref)) is not None:
        return year
    explicit = _YEAR.search(citation.replace(ref, " "))
    return int(explicit.group(1)) if explicit else None


def parse_amendments(text: str) -> list[tuple[str | None, str]]:
    """(amended article number or None, amending text's number) for each footnote."""
    return [(event.article, event.ref) for event in parse_events(text)]


def summarize(texts: list[str]) -> dict:
    """Amending texts (most frequent first, with their year), per article which texts changed
    it, and per article a chronological history of how."""
    by_law: dict[str, set[str]] = defaultdict(set)
    mentions: dict[str, int] = defaultdict(int)
    years: dict[str, int | None] = {}
    by_article: dict[str, set[str]] = defaultdict(set)
    events: dict[str, dict[str, dict]] = defaultdict(dict)  # article → ref → entry
    for text in texts:
        for event in parse_events(text):
            mentions[event.ref] += 1
            years[event.ref] = years.get(event.ref) or event.year
            if event.article:
                by_law[event.ref].add(event.article)
                by_article[event.article].add(event.ref)
                entry = events[event.article].setdefault(event.ref, {"ref": event.ref, "kinds": [], "year": event.year})
                entry["kinds"] = list(dict.fromkeys([*entry["kinds"], *event.kinds]))
                entry["year"] = entry["year"] or event.year
    laws = [
        {"ref": ref, "mentions": n, "articles": sorted(by_law[ref], key=_article_key), "year": years[ref]}
        for ref, n in sorted(mentions.items(), key=lambda kv: -kv[1])
    ]
    history = {
        article: sorted(entries.values(), key=lambda e: (e["year"] is None, e["year"] or 0, e["ref"]))
        for article, entries in events.items()
    }
    return {"laws": laws, "articles": {a: sorted(refs) for a, refs in by_article.items()}, "history": history}


def _article_key(number: str) -> tuple[int, ...]:
    return tuple(int(p) for p in number.split("-") if p.isdigit())
