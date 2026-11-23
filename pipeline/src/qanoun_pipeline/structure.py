"""Segment a law's pages into ordered articles — the unit the whole product cites.

Article headers are matched on the display text ("المادة 12", "Article 12"); numbers are
normalized so Arabic-Indic digits (١٢) and glued footnotes ("Article 23" + note 17 →
"2317") still resolve. Sub-numbered articles ("Article 65-1", "المادة 65 مكرر") keep their
suffix so they stay unique. Everything before the first header becomes the law's preamble.
A StructureReport carries warnings (number gaps, duplicates) so bad OCR shows up as
data-quality signal instead of silent corruption.
"""

import re
from dataclasses import dataclass, field
from itertools import pairwise

from qanoun_pipeline.parse import Page

# Header patterns. Real files glue the number to the word ("المادة1"), write "Article
# premier" for 1, and use sub-numbers ("65-1", "65 مكرر") — all must match.
_ARABIC_DIGITS = r"([0-9٠-٩]+)(?:\s*[-–]\s*([0-9٠-٩]+)|\s+(مكرر|مكررة))?"
_FRENCH_HEADER = re.compile(r"^\s*(?:Article|ARTICLE)\s+(premier|\d+)(?:er)?(?:\s*[-–]\s*(\d+))?")
# The D.O.C. says "الفصل" where every other code says "المادة" — the words are per-law
# (catalog field article_words) so "الفصل" as chapter/dismissal elsewhere can't misfire.
DEFAULT_ARTICLE_WORDS = ("المادة", "مادة")
# Many laws write their first article in words: «المادة الأولى» (and, with the PDFs' lam-alef
# artifact, «المادة األولى»). Only accepted before any other article, where article 1 belongs.
_FIRST_ARTICLE_IN_WORDS = re.compile(r"^\s*(?:المادة|مادة)\s*[:：]?\s*(?:الأولى|األولى|االولى|الاولى)(?!\S)")
_DIGITS = str.maketrans({chr(0x0660 + i): str(i) for i in range(10)} | {chr(0x06F0 + i): str(i) for i in range(10)})


def arabic_header_re(words: tuple[str, ...] = DEFAULT_ARTICLE_WORDS) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in words)
    return re.compile(rf"^\s*(?:{alts})\s*[:：]?\s*{_ARABIC_DIGITS}")


# A header rebuilt from two lines may also be a reference that wrapped («… عليها في» /
# «المادة» / «95»): accept it only when it moves the numbering forward by at most this much
# (repealed articles leave small gaps), or is a sub-article of the current one.
MAX_JOINED_GAP = 10


# How a header line was rebuilt (None: read as is).
JOINED = "joined"  # «المادة» / «26»: the word, then its number on the next line
SPLIT_SUB = "split-sub"  # «الفصل1» / «-» / «218»: a sub-article over three lines, either order


def _lines(text: str, words: tuple[str, ...]):
    """(line, how) for each non-empty line, with split headers joined back.

    Some PDFs put the word and its number on separate lines («المادة» / «26»: half the
    Arabic Commercial Code hid inside its neighbours). Right-to-left extraction also splits a
    sub-article header over three lines and reverses it: «الفصل 218-1» comes out «الفصل1» /
    «-» / «218», which read as article 1 (a duplicate, so its text joined article 218).
    """
    alts = "|".join(re.escape(w) for w in (*words, "Article", "ARTICLE"))
    word_only = re.compile(rf"^\s*(?:{alts})\s*[:：]?\s*$")
    word_number = re.compile(rf"^\s*((?:{alts}))\s*[:：]?\s*([0-9٠-٩]+)\s*$")
    dash = re.compile(r"^\s*[-–]\s*$")
    number = re.compile(r"^\s*([0-9٠-٩]+)\s*$")
    lines = [raw for raw in text.splitlines() if raw.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            (head := word_number.match(line)) is not None
            and i + 2 < len(lines)
            and dash.match(lines[i + 1])
            and (tail := number.match(lines[i + 2])) is not None
        ):
            yield f"{head.group(1)} {head.group(2)} - {tail.group(1)}", SPLIT_SUB
            i += 3
            continue
        if word_only.match(line) and i + 1 < len(lines) and re.match(r"\s*(?:[0-9٠-٩]|premier\b)", lines[i + 1]):
            yield f"{line.strip()} {lines[i + 1].strip()}", JOINED
            i += 2
            continue
        yield line, None
        i += 1


def _plausible_joined(base: int, has_suffix: bool, seen: list[int]) -> bool:
    if not seen:
        return True
    if has_suffix:
        return base == seen[-1]
    return seen[-1] < base <= seen[-1] + MAX_JOINED_GAP


@dataclass(frozen=True)
class ArticleDraft:
    number: str
    ordinal: int  # 1-based position in the law, regardless of numbering gaps
    text: str
    page_start: int
    page_end: int


@dataclass
class StructureReport:
    preamble: str = ""
    articles: list[ArticleDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StructureError(RuntimeError):
    pass


def _repair_sequence(digits: str, seen: list[int]) -> tuple[int, bool]:
    """Recover the article number when a footnote index got glued to the header.

    The D.O.C. PDF renders superscript footnotes in the same text run, so "Article 23"
    plus footnote 17 extracts as "Article 2317". Article numbers run consecutively, so if
    the captured value skips ahead, the longest prefix equal to the expected next number
    wins. No previous numbers (or already correct) → accept as captured.
    """
    number = int(digits)
    expected = seen[-1] + 1 if seen else None
    if expected is not None and number != expected:
        for cut in range(len(digits) - 1, 0, -1):
            if digits[:cut].isdigit() and int(digits[:cut]) == expected:
                return expected, True
    return number, False


def segment(
    pages: list[Page], article_words: tuple[str, ...] = DEFAULT_ARTICLE_WORDS
) -> StructureReport:
    """Split page texts into articles. Raises StructureError when no header is found at all."""
    arabic_header = arabic_header_re(article_words)
    report = StructureReport()
    preamble_lines: list[str] = []
    current: dict | None = None  # {"number", "text", "page_start"}
    seen_bases: list[int] = []
    seen_numbers: set[str] = set()

    def close(page_end: int) -> None:
        nonlocal current
        if current is not None:
            text = " ".join(current["text"]).strip()
            if text:
                report.articles.append(
                    ArticleDraft(
                        number=current["number"],
                        ordinal=len(report.articles) + 1,
                        text=text,
                        page_start=current["page_start"],
                        page_end=page_end,
                    )
                )
            current = None

    for page in pages:
        for line, how in _lines(page.text, article_words):
            if (ar := arabic_header.match(line)) is not None:
                digits = ar.group(1).translate(_DIGITS)
                sub = ar.group(2) or ar.group(3)
            elif (fr := _FRENCH_HEADER.match(line)) is not None:
                digits = fr.group(1).translate(_DIGITS)
                sub = fr.group(2)
            elif not seen_bases and _FIRST_ARTICLE_IN_WORDS.match(line):
                digits, sub = "1", None
            else:
                target = current["text"] if current is not None else preamble_lines
                target.append(line.strip())
                continue
            digits = "1" if digits == "premier" else digits
            if how == SPLIT_SUB:
                # A sub-article of the article in progress: «1 - 218» after 218 is 218-1
                # (right-to-left order), «218 - 1» is the same in reading order.
                first, second = int(digits), int(sub.translate(_DIGITS))
                open_base = seen_bases[-1] if seen_bases else None
                parent, child = (
                    (second, first) if second == open_base else (first, second) if first == open_base else (None, None)
                )
                if parent is None:
                    target = current["text"] if current is not None else preamble_lines
                    target.append(line.strip())
                    continue
                digits, sub = str(parent), str(child)
            elif sub and sub.isdigit() and seen_bases:
                # Same reversal on one line: «المادة4 - 10» after article 10 is 10-4.
                first, second = int(digits.translate(_DIGITS)), int(sub.translate(_DIGITS))
                if second == seen_bases[-1] and first != seen_bases[-1]:
                    digits, sub = str(second), str(first)
            base, trimmed = _repair_sequence(digits, seen_bases)
            suffix = f"-{sub.translate(_DIGITS)}" if sub and sub.isdigit() else "-bis" if sub else ""
            number = f"{base}{suffix}"
            if how == JOINED and not _plausible_joined(base, bool(suffix), seen_bases):
                target = current["text"] if current is not None else preamble_lines
                target.append(line.strip())
                continue
            if number in seen_numbers:
                # Footnote text and amendment notes also start with "Article …". Keeping the
                # first occurrence (the real header) leaves such lines in the article body.
                report.warnings.append(f"duplicate header for article {number} — kept as body text")
                target = current["text"] if current is not None else preamble_lines
                target.append(line.strip())
                continue
            close(page.page)
            if trimmed:
                report.warnings.append(f"trimmed glued footnote from header: {digits} → {base}")
            current = {"number": number, "text": [line.strip()], "page_start": page.page}
            seen_numbers.add(number)
            if not suffix:
                seen_bases.append(base)
    close(pages[-1].page if pages else 0)

    if not report.articles:
        raise StructureError(
            "no article headers found — the text layer is probably unusable; "
            "re-ingest with OCR enabled"
        )
    report.preamble = " ".join(preamble_lines).strip()

    numbers = [int(a.number.split("-")[0]) for a in report.articles]
    for previous, number in pairwise(numbers):
        if number < previous:
            report.warnings.append(f"article numbers go {previous} → {number} (out of order)")
    if report.preamble and len(report.preamble) < 60:
        report.warnings.append("suspiciously short preamble — headers may be misdetected")
    return report
