"""Cross-references between articles: «المنصوص عليها في المادة 53 أعلاه», «l'article 12 ci-dessus».

Derived only from article text already in the database, so `rebuild(conn)` recomputes every
link without the PDFs or any embedding; ingestion runs it after loading. Links are stored as
(article_id → target law slug, target number) and matched to articles when read: a link
survives a re-ingest of the law it points to (which recreates that law's article rows).

Rules, from a survey of the corpus:
- Arabic: المادة / المواد / المادتين and the D.O.C.'s الفصل / الفصول, with their prefixes
  (للمادة، بالمادة، والمادة) and the number often glued («المادة53»); lists and ranges
  («المواد 12 و13 و14», «من 10 إلى 15»). French: article(s) N, et, à, bis.
- Same law when unqualified or qualified as such (أعلاه، أدناه، من هذا القانون, ci-dessus,
  du présent code). Another law when followed by its number («من القانون رقم 15.95»,
  «de la loi n° 70-03») or its title («من مدونة الأسرة»); a text we do not have, or one named
  without a resolvable number («من المرسوم السالف الذكر»), is dropped rather than guessed.
- Amendment notes («تم تغيير المادة 98 أعلاه», «modifié par …») are not references.
- Section headings that list their articles («(Articles 248 à 256)») are not references.
- Only exact targets are linked. Right-to-left extraction reverses sub-article numbers
  («المادة 157-10» comes out «10 - 157», and is stored that way too), and a sub-article's
  misplaced header («الفصل1 - 218» inside article 218) looks like a reference to article 1:
  guessing the base number would link the wrong article, so a target the law lacks is dropped.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

import psycopg

_DIGITS = str.maketrans({chr(0x0660 + i): str(i) for i in range(10)} | {chr(0x06F0 + i): str(i) for i in range(10)})
_NUM = r"\d+(?:\s*[-–]\s*\d+)?(?:\s*(?:مكررة|مكرر|bis))?"

_AR_REF = re.compile(
    r"(?<![\w])[وف]?(?:بال|لل|ال|كال)(?:مادتين|مادتان|مادة|مواد|فصلين|فصلان|فصول|فصل)\s*"
    rf"({_NUM}(?:\s*(?:،|,|و|أو|إلى|الى)\s*(?:المادة|الفصل)?\s*{_NUM})*)"
)
_FR_REF = re.compile(
    r"(?i)\b(?:l['’]\s*|aux\s+|des\s+|les\s+)?articles?\s+"
    rf"((?:premier|{_NUM})(?:\s*(?:,|et|à|ou)\s*{_NUM})*)"
)
_OWN_HEADER = re.compile(r"^\s*(?:المادة|مادة|الفصل|Article|ARTICLE)\s*[\d\-]+\s*(?:مكرر|bis)?\s*[.:-]?")
_AMENDMENT = re.compile(
    r"تم\s*(?:تغيير|نسخ|تتميم|تعديل|تعويض|إلغاء)|تمت?\s*إضافة|أضيفت|نسخت|غيرت|ألغيت|[أا]نظر\s*هامش"
    r"|(?i:modifi[ée]|abrog[ée]|compl[ée]t[ée]|remplac[ée]|ajout[ée]|ins[ée]r[ée]|voir\s+note)"
)
_SAME_LAW = re.compile(
    r"(?i)^\s*(?:أعلاه|اعلاه|أ\s?عاله|أدناه|ادناه|بعده|بعدها|قبله|من\s+هذا\s+(?:القانون|الظهير|المرسوم)"
    r"|من\s+هذه\s+المدونة|ci-?\s?dessus|ci-?\s?dessous|du\s+présent|de\s+la\s+présente|précit)"
)
_OTHER_BY_NUMBER = re.compile(
    r"(?i)^\s*(?:من|de\s+la|du)\s+(?:القانون|الظهير(?:\s*الشريف)?|المرسوم|loi|dahir|décret)\s*"
    r"(?:رقم|n°|no|n\.)?\s*([0-9][0-9.\-/]*[0-9])"
)
_OTHER_TEXT = re.compile(
    r"(?i)^\s*(?:من\s+(?:ال)?(?:قانون|ظهير|مرسوم|قرار|مدونة)"
    r"|de\s+la\s+loi|du\s+dahir|du\s+décret|du\s+code|de\s+l['’]arrêté)"
)


@dataclass(frozen=True)
class Law:
    slug: str
    language: str
    law_number: str | None
    title: str  # in the law's own language


@dataclass(frozen=True)
class Reference:
    target_slug: str
    number: str  # as written, normalized ("65-1", "12-bis"); resolved against the target later
    raw: str


def _law_key(number: str | None) -> str:
    return re.sub(r"[.\-/\s]", "", number or "")


def _numbers(listing: str) -> list[str]:
    out = []
    for raw in re.findall(_NUM, listing):
        m = re.match(r"(\d+)\s*(?:[-–]\s*(\d+))?\s*(مكررة|مكرر|bis)?", raw)
        base, sub, bis = m.groups()
        out.append(f"{base}-{sub}" if sub else f"{base}-bis" if bis else base)
    if (span := re.search(r"(\d+)\s*(?:إلى|الى|à)\s*(\d+)", listing)) is not None:
        first, last = int(span.group(1)), int(span.group(2))
        if 0 < last - first <= 30:
            out += [str(n) for n in range(first, last + 1)]
    if listing.strip().lower().startswith("premier"):
        out.append("1")
    return list(dict.fromkeys(out))


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".؛\n")
    rights = [i for i in (text.find(c, end) for c in ".؛\n") if i != -1]
    return text[left + 1 : min(rights) if rights else len(text)]


class Resolver:
    """Which law a reference points to, from the laws in the database."""

    def __init__(self, laws: Iterable[Law]):
        self.laws = list(laws)
        self.by_number = {(law.language, _law_key(law.law_number)): law.slug for law in self.laws if law.law_number}
        # longest titles first, so «مدونة التجارة» is not matched by a shorter title
        self.by_title = sorted(
            ((law.title, law.language, law.slug) for law in self.laws if law.title),
            key=lambda t: -len(t[0]),
        )

    def extract(self, slug: str, language: str, own_number: str, text: str) -> list[Reference]:
        text = text.translate(_DIGITS)
        body = _OWN_HEADER.sub("", text, count=1)
        pattern = _AR_REF if language == "ar" else _FR_REF
        refs: list[Reference] = []
        for match in pattern.finditer(body):
            if body[: match.start()].rstrip().endswith("("):  # a section heading's article list
                continue
            if _AMENDMENT.search(_sentence(body, match.start(), match.end())):
                continue
            tail = body[match.end() : match.end() + 80]
            target = self._target(slug, language, tail)
            if target is None:
                continue
            for number in _numbers(match.group(1)):
                if target == slug and number == own_number:
                    continue
                refs.append(Reference(target, number, match.group(0).strip()))
        return refs

    def _target(self, slug: str, language: str, tail: str) -> str | None:
        if _SAME_LAW.match(tail):
            return slug
        if (by_number := _OTHER_BY_NUMBER.match(tail)) is not None:
            return self.by_number.get((language, _law_key(by_number.group(1))))
        if _OTHER_TEXT.match(tail):
            head = tail[:90]
            return next((s for title, lang, s in self.by_title if lang == language and title in head), None)
        return slug  # unqualified: this law


REFS_SQL_LAWS = "SELECT slug, language, law_number, CASE WHEN language = 'ar' THEN title_ar ELSE COALESCE(title_fr, title_ar) END FROM laws"
REFS_SQL_ARTICLES = "SELECT a.id, l.slug, l.language, a.number, a.text FROM articles a JOIN laws l ON l.id = a.law_id"


def resolve_number(number: str, existing: set[str]) -> str | None:
    """The target article as stored, only if it exists exactly (see the module notes)."""
    return number if number in existing else None


def rebuild(conn: psycopg.Connection) -> int:
    """Recompute every article reference from the articles in the database; return the count."""
    resolver = Resolver(Law(*row) for row in conn.execute(REFS_SQL_LAWS).fetchall())
    articles = conn.execute(REFS_SQL_ARTICLES).fetchall()
    numbers: dict[str, set[str]] = {}
    for _, slug, _, number, _ in articles:
        numbers.setdefault(slug, set()).add(number)
    rows: dict[tuple[int, str, str], str] = {}
    for article_id, slug, language, number, text in articles:
        for ref in resolver.extract(slug, language, number, text):
            target = resolve_number(ref.number, numbers.get(ref.target_slug, set()))
            if target is None or (ref.target_slug == slug and target == number):
                continue
            rows.setdefault((article_id, ref.target_slug, target), ref.raw[:200])
    with conn.transaction():
        conn.execute("DELETE FROM article_refs")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO article_refs (article_id, target_law_slug, target_number, raw) VALUES (%s, %s, %s, %s)",
                [(*key, raw) for key, raw in rows.items()],
            )
    return len(rows)
