"""Seed catalog: the laws Qanoun ingests, with multilingual metadata and provenance.

One YAML entry per document file. A bilingual law (official Arabic edition + French
translation) has two entries sharing a `group`, so the UI can show editions side by side
while retrieval treats each file as one document.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DOMAINS = {
    "family",       # مدونة الأسرة: marriage, engagement, divorce, custody
    "labour",       # مدونة الشغل: work, contracts, wages, leave
    "civil",        # قانون الالتزامات والعقود: contracts, obligations
    "housing",      # كراء العقارات: leases, rentals
    "commercial",   # commercial leases, business law, competition
    "education",    # schools, high schools, universities
    "penal",        # criminal law
    "nationality",  # citizenship
    "social",       # social security, insurance, pensions
    "justice",      # courts, procedure, judicial organization
    "transport",    # traffic code, road accident compensation
    "property",     # land registration, real rights, urbanism
    "governance",   # associations, press, unions, data protection, public finance
}
LANGUAGES = {"ar", "fr"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LawMeta:
    slug: str
    group: str
    title_ar: str
    title_fr: str | None
    law_number: str | None
    year: int | None
    domain: str
    language: str
    file: str
    source_url: str | None
    sha256: str | None
    article_words: tuple[str, ...] = ("المادة", "مادة")

    @property
    def title(self) -> str:  # convenience for CLI prints (a property can't take a language)
        return self.title_ar


class CatalogError(ValueError):
    pass


def load(path: Path | str) -> list[LawMeta]:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    # The file wraps entries under a top-level `entries:` key; accept both shapes.
    if isinstance(data, dict):
        data = data.get("entries", [])
    laws = []
    for i, raw in enumerate(data):
        try:
            laws.append(_parse(raw))
        except CatalogError as exc:
            raise CatalogError(f"catalog entry #{i + 1} ({raw.get('slug', '?')}): {exc}") from exc
    slugs = [law.slug for law in laws]
    if len(slugs) != len(set(slugs)):
        raise CatalogError("duplicate slugs in catalog")
    return laws


def _parse(raw: dict) -> LawMeta:
    slug = _require(raw, "slug")
    domain = _require(raw, "domain")
    if domain not in DOMAINS:
        raise CatalogError(f"unknown domain '{domain}' (allowed: {sorted(DOMAINS)})")
    language = _require(raw, "language")
    if language not in LANGUAGES:
        raise CatalogError(f"unknown language '{language}'")
    sha256 = raw.get("sha256")
    if sha256 is not None and not _SHA256.match(sha256):
        raise CatalogError("sha256 must be 64 lowercase hex chars")
    article_words = raw.get("article_words")
    return LawMeta(
        slug=slug,
        group=raw.get("group") or slug,
        title_ar=_require(raw, "title_ar"),
        title_fr=raw.get("title_fr"),
        law_number=raw.get("law_number"),
        year=raw.get("year"),
        domain=domain,
        language=language,
        file=_require(raw, "file"),
        source_url=raw.get("source_url"),
        sha256=sha256,
        # e.g. article_words: الفصل,فصل for the D.O.C.; المادة,مادة everywhere else
        article_words=tuple(w.strip() for w in article_words.split(",")) if article_words
        else ("المادة", "مادة"),
    )


def _require(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not value or not isinstance(value, str):
        raise CatalogError(f"missing or invalid required field '{key}'")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
