"""Watch the Ministry of Justice portal for updated texts of the laws in the catalog.

    uv run --project pipeline python scripts/watch_portal.py [--dry-run] [--report report.md]

The portal (adala.justice.gov.ma) publishes an updated consolidated text as a new upload, under
a dated path (uploads/YYYY/MM/DD/...), and keeps serving the old one. So for each catalog entry
this searches the portal by the law's number (its title when it has none) and takes a result
as a candidate update when it is the same kind of text, in the same language, carries the same
number, and was uploaded after the catalog's file. A candidate is downloaded and kept only if
its sha256 differs and it still segments into at least 80% of the current file's articles: a
partial or broken upload never replaces a good one.

It also reads the portal's «latest releases» and lists new texts that cite a law we carry
(an implementing decree, an amending law), for a person to decide on.

Without --dry-run it rewrites `source_url` and `sha256` of the updated entries in
data/catalog/laws.yaml; the weekly workflow then opens a pull request with the report. It never
ingests: after merging, `make ingest` (or `ingest-all --slugs`) fetches and verifies the files.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx
from qanoun_pipeline import catalog
from qanoun_pipeline.cli import segment_pdf
from qanoun_pipeline.structure import StructureError

PORTAL = "https://adala.justice.gov.ma"
CATALOG = Path("data/catalog/laws.yaml")
HEADERS = {"User-Agent": "qanoun-portal-watch/0.2 (+https://github.com/scorpionTaj/qanoun)"}
# Portal text types that are legislation (not studies, circulars or speeches). A law is only
# matched to laws and a decree to decrees: a decree applying law 114.13 carries its number too.
LAW_TYPES = {"ظهير", "قانون", "قانون تنظيمي", "دستور", "Dahir", "Loi", "Constitution"}
DECREE_TYPES = {"مرسوم", "Décret"}
_DATE = re.compile(r"uploads/(\d{4})/(\d{2})/(\d{2})/")
MIN_ARTICLE_SHARE = 0.8


@dataclass
class Update:
    slug: str
    old_url: str
    new_url: str
    name: str
    old_articles: int
    new_articles: int
    sha256: str


def upload_date(url_or_path: str) -> str | None:
    m = _DATE.search(urllib.parse.unquote(url_or_path))
    return "".join(m.groups()) if m else None


def number_forms(law_number: str | None) -> list[str]:
    """How a catalog number («65-99», «1-74-447», «2.04.569») is printed in portal names."""
    if not law_number or not re.search(r"\d+[.\-]\d+", law_number):
        return []
    parts = re.split(r"[.\-]", law_number)
    return [".".join(parts), "-".join(parts)]


def search(client: httpx.Client, term: str, lang: str) -> dict:
    """The portal's search page embeds its results (and the latest releases) as page data."""
    url = f"{PORTAL}/{lang}/search?term={urllib.parse.quote(term)}"
    html = client.get(url).text
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    return json.loads(m.group(1))["props"]["pageProps"] if m else {}


def is_decree(law_number: str | None) -> bool:
    """Moroccan decrees are numbered 2.YY.NNN (dahirs 1.YY.NNN, laws NN.YY)."""
    return bool(law_number and re.match(r"^2[.\-]\d{2}[.\-]\d+$", law_number))


def candidates(meta: catalog.LawMeta, results: list[dict]) -> list[dict]:
    forms = number_forms(meta.law_number)
    current = upload_date(meta.source_url or "")
    types = DECREE_TYPES if is_decree(meta.law_number) else LAW_TYPES
    found = []
    for r in results:
        kind = ((r.get("fileMeta") or {}).get("LawType") or {}).get("name", "")
        if r.get("type") != "PDF" or kind not in types or r.get("language", "").lower() != meta.language:
            continue
        text = f"{r.get('name', '')} {urllib.parse.unquote(r.get('path', ''))}"
        if forms and not any(f in text for f in forms):
            continue
        if not forms and meta.title_ar not in text:
            continue
        date = upload_date(r.get("path", ""))
        if current and date and date > current:
            found.append(r)
    return sorted(found, key=lambda r: upload_date(r["path"]), reverse=True)


def article_count(client: httpx.Client, url: str, meta: catalog.LawMeta, folder: Path) -> tuple[int, str] | None:
    """Download a PDF; return (articles, sha256), or None if it is not a PDF. Articles are
    counted exactly as ingestion counts them (text layer, OCR fallback), so a law whose text
    layer is broken (the Arabic Labour Code) is not judged on its broken layer."""
    response = client.get(url)
    if response.status_code != 200 or not response.content.startswith(b"%PDF"):
        return None
    sha256 = hashlib.sha256(response.content).hexdigest()
    path = folder / f"{meta.slug}-{sha256[:8]}.pdf"  # stable name: the OCR cache is reused
    path.write_bytes(response.content)
    try:
        articles = len(segment_pdf(path, meta)[0].articles)
    except StructureError:
        articles = 0
    return articles, sha256


def cited_new_texts(releases: list[dict], laws: list[catalog.LawMeta]) -> list[tuple[str, str]]:
    """Latest releases whose title cites one of our laws' numbers: (our slug, release title)."""
    hits = []
    for release in releases:
        title = f"{release.get('object') or ''} {release.get('title') or ''}"
        for law in laws:
            if any(f"رقم {f}" in title or f"n° {f}" in title for f in number_forms(law.law_number)):
                hits.append((law.slug, (release.get("title") or release.get("object") or "")[:200]))
                break
    return hits


def rewrite_catalog(path: Path, updates: list[Update]) -> None:
    """Replace source_url and sha256 of updated entries, keeping the file's layout."""
    by_slug = {u.slug: u for u in updates}
    lines, current = path.read_text(encoding="utf-8").split("\n"), None
    for i, line in enumerate(lines):
        if line.startswith("- slug: "):
            current = by_slug.get(line.split(": ", 1)[1].strip())
        elif current and line.startswith("  source_url: "):
            lines[i] = f"  source_url: {current.new_url}"
        elif current and line.startswith("  sha256: "):
            lines[i] = f"  sha256: {current.sha256}"
    path.write_text("\n".join(lines), encoding="utf-8")


def report(updates: list[Update], cited: list[tuple[str, str]], checked: int) -> str:
    out = [f"Weekly check of {checked} catalog texts against adala.justice.gov.ma.", ""]
    if updates:
        out += ["## Updated texts (catalog changed in this PR)", "",
                "| law | articles (old → new) | new upload |", "|---|---|---|"]
        out += [f"| `{u.slug}` | {u.old_articles} → {u.new_articles} | [{u.name[:80]}]({u.new_url}) |" for u in updates]
        out += ["", "After merging: `uv run --project pipeline python -m qanoun_pipeline.cli ingest-all --slugs "
                + ",".join(u.slug for u in updates) + "` (fetches and verifies the new files), then the eval gate."]
    else:
        out += ["No updated text found."]
    if cited:
        out += ["", "## New texts on the portal that cite our laws (not ingested; decide case by case)", ""]
        out += [f"- `{slug}`: {title}" for slug, title in cited]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only, leave the catalog as is")
    parser.add_argument("--report", type=Path, help="write the Markdown report here")
    parser.add_argument("--slugs", help="comma-separated: only these catalog entries")
    args = parser.parse_args()

    laws = catalog.load(CATALOG)
    if args.slugs:
        wanted = set(args.slugs.split(","))
        laws = [law for law in laws if law.slug in wanted]
    updates: list[Update] = []
    releases: list[dict] = []
    folder = Path("data/raw/_watch")
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=180, follow_redirects=True, headers=HEADERS) as client:
        for law in laws:
            term = number_forms(law.law_number)[0] if number_forms(law.law_number) else law.title_ar
            page = search(client, term, law.language)
            releases = releases or page.get("latestReleases") or []
            found = candidates(law, (page.get("searchResult") or {}).get("data") or [])
            if not found:
                continue
            new_url = f"{PORTAL}/api/{urllib.parse.quote(found[0]['path'])}"
            new = article_count(client, new_url, law, folder)
            old = article_count(client, law.source_url, law, folder) if law.source_url else None
            if new is None or (law.sha256 and new[1] == law.sha256):
                continue
            old_articles = old[0] if old else 0
            if old_articles and new[0] < MIN_ARTICLE_SHARE * old_articles:
                print(f"  {law.slug}: newer upload segments into {new[0]} articles (was {old_articles}), skipped")
                continue
            updates.append(Update(law.slug, law.source_url or "", new_url, found[0].get("name", ""),
                                  old_articles, new[0], new[1]))
            print(f"  {law.slug}: updated text found ({old_articles} → {new[0]} articles)")
    cited = cited_new_texts(releases, laws)
    text = report(updates, cited, len(laws))
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    if updates and not args.dry_run:
        rewrite_catalog(CATALOG, updates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
