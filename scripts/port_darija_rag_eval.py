"""One-off: port darija-rag's question set to Qanoun's eval format.

    uv run --project pipeline python scripts/port_darija_rag_eval.py ../darija-rag/eval/questions.jsonl

darija-rag labels each question with the PDF pages that answer it. Qanoun retrieves
articles, not pages, and both projects read the same PDFs (same sha256 in the catalog), so
each labelled page becomes the articles printed on it: `expected_page_articles`. A hit on
any of them counts, which is darija-rag's own criterion (a retrieved chunk on a labelled
page). The original pages are kept under `pages` for audit.

Most reference answers also cite the article that answers ("المادة 4", "article 3",
"lmadda 209"). When that article is on a labelled page it becomes `expected_articles`:
the strict target.

Not ported: darija-rag's "unanswerable" questions. They were out of scope for its 8
documents (e.g. theft in the penal code) but Qanoun's corpus contains those laws.

Re-run after re-ingesting with different segmentation: article boundaries decide which
articles sit on a page.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from qanoun_pipeline import catalog
from qanoun_pipeline.cli import CATALOG, _process_file

VARIETY = {"msa": "msa", "darija": "darija", "arabizi": "arabizi", "fr": "other"}
# Article numbers cited in a reference answer: "المادة 4", "للمادة 175", "المادتان 94 و95",
# "الفصلان 77 و78", "articles 269 et 270", "art. 3", and Arabizi "lmadda 209".
_CITED = re.compile(
    r"(?:\w*ماد[ةت]\w*|\w*فصل\w*|[Aa]rticles?|art\.|l?madda|l?fasl)\s*(\d+)(?:\s*(?:و|et|w)\s*(\d+))?"
)


def articles_by_page(meta: catalog.LawMeta) -> dict[int, list[str]]:
    """Page number → numbers of the articles printed on it, segmented as at ingest."""
    report, _ = _process_file(meta, argparse.Namespace(skip_fetch=True))
    pages: dict[int, list[str]] = {}
    for article in report.articles:
        for page in range(article.page_start, article.page_end + 1):
            pages.setdefault(page, []).append(article.number)
    return pages


def port(source: Path, laws: list[catalog.LawMeta]) -> tuple[list[dict], Counter]:
    by_file = {law.file: law for law in laws}
    page_index: dict[str, dict[int, list[str]]] = {}
    ported, skipped = [], Counter()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        if not q["relevant"]:
            skipped["unanswerable in darija-rag"] += 1
            continue
        targets: list[list[str]] = []
        for ref in q["relevant"]:
            meta = by_file[ref["doc"]]
            if meta.file not in page_index:
                page_index[meta.file] = articles_by_page(meta)
            for number in page_index[meta.file].get(ref["page"], []):
                if [meta.group, number] not in targets:
                    targets.append([meta.group, number])
        if not targets:
            skipped["no article on the labelled pages"] += 1
            continue
        cited = {number for pair in _CITED.findall(q["answer"]) for number in pair if number}
        row = {
            "id": f"drag-{q['id']}",
            "question": q["question"],
            "variety": VARIETY[q["lang"]],
            "type": q["type"],
            "expected_page_articles": targets,
            "pages": [[by_file[ref["doc"]].slug, ref["page"]] for ref in q["relevant"]],
        }
        exact = [target for target in targets if target[1] in cited]
        if exact:
            row["expected_articles"] = exact
        elif cited:
            skipped["cited article not found on the labelled pages (page-level only)"] += 1
        ported.append(row)
    return ported, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="darija-rag eval/questions.jsonl")
    parser.add_argument("--out", type=Path, default=Path("data/eval/pages.jsonl"))
    args = parser.parse_args()

    ported, skipped = port(args.source, catalog.load(CATALOG))
    with args.out.open("w", encoding="utf-8") as f:
        for q in ported:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    varieties = Counter(q["variety"] for q in ported)
    sizes = sorted(len(q["expected_page_articles"]) for q in ported)
    print(f"ported {len(ported)} questions → {args.out}  {dict(varieties)}")
    print(f"articles per question: median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    print(f"with a strict (cited) article: {sum('expected_articles' in q for q in ported)}")
    for reason, count in skipped.items():
        print(f"skipped {count}: {reason}")


if __name__ == "__main__":
    main()
