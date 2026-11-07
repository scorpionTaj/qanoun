"""CLI for the Qanoun data-engineering pipeline.

    uv run --project pipeline python -m qanoun_pipeline.cli ingest-all [--skip-fetch]
        [--domains family,labour] [--ocr-glob '*_ar.pdf'] [--fake-embed] [--dry-run]

Run from the repo root. `ingest-all` chains: fetch → parse (OCR fallback) → structure →
chunk → embed → load into Postgres/pgvector, then prints a per-law summary.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from qanoun_pipeline import catalog, chunk, load_db, parse, structure
from qanoun_pipeline import embed as embed_mod
from qanoun_pipeline.normalize import normalize
from qanoun_pipeline.sources import fetch

DEFAULT_DB = "postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun"
CATALOG = Path("data/catalog/laws.yaml")
RAW_DIR = Path("data/raw")
PROCESSED = Path("data/processed")

ARTICLES_JSONL = PROCESSED / "articles.jsonl"
CHUNKS_JSONL = PROCESSED / "chunks.jsonl"


def ingest_all(args: argparse.Namespace) -> int:
    laws = catalog.load(args.catalog)
    if args.domains:
        wanted = {d.strip() for d in args.domains.split(",")}
        unknown = wanted - {law.domain for law in laws}
        if unknown:
            sys.exit(f"unknown domains: {sorted(unknown)}")
        laws = [law for law in laws if law.domain in wanted]
    if args.limit:
        laws = laws[: args.limit]
    print(f"catalog: {len(laws)} file(s) selected")

    if not args.skip_fetch:
        for path in fetch.ensure_corpus(laws, RAW_DIR):
            print(f"  have {path.name}")

    if args.fake_embed:
        # 1024-dim to match the pgvector column; content is hash-based, not semantic.
        embedder = embed_mod.fake_embedder(dim=1024, cache_dir=PROCESSED / "embeddings")
        print("embeddings: FAKE (smoke test — do not ship)")
    else:
        embedder = embed_mod.Embedder(cache_dir=PROCESSED / "embeddings")
    print(f"embeddings: {embedder.spec.name} (dim {embedder.spec.dim})")

    article_rows: list[dict] = []
    chunk_rows: list[dict] = []
    ingested: list[tuple[catalog.LawMeta, structure.StructureReport, int]] = []
    failed: list[tuple[str, str]] = []
    for meta in laws:
        try:
            report, page_count = _process_file(meta, args)
        except Exception as exc:  # noqa: BLE001 — one broken file must not kill a 40-law run
            failed.append((meta.slug, str(exc)[:120]))
            print(f"  ✗ {meta.slug}: FAILED — {str(exc)[:120]}")
            continue
        law_articles = [
            {
                "law_slug": meta.slug,
                "number": a.number,
                "ordinal": a.ordinal,
                "text": a.text,
                "normalized": " ".join(normalize(a.text).split()),
                "page_start": a.page_start,
                "page_end": a.page_end,
            }
            for a in report.articles
        ]
        law_chunks: list[dict] = []
        for article, arow in zip(report.articles, law_articles, strict=True):
            for piece in chunk.chunk_article(meta.slug, article, size=args.chunk_size, overlap=args.chunk_overlap):
                law_chunks.append({**piece.as_dict(), "passage": _passage_text(meta, article, piece.text)})
        vectors = embedder.encode_passages([c["passage"] for c in law_chunks])
        for c, vector in zip(law_chunks, vectors, strict=True):
            c["embedding"] = vector

        article_rows.extend(law_articles)
        chunk_rows.extend(law_chunks)
        ingested.append((meta, report, page_count))
        warnings = "; ".join(report.warnings) or "-"
        print(f"  {meta.slug}: {len(law_articles)} articles, {len(law_chunks)} chunks (warnings: {warnings})")
    if failed:
        print(f"\n{len(failed)} file(s) failed and were skipped: {[slug for slug, _ in failed]}")

    PROCESSED.mkdir(parents=True, exist_ok=True)
    _write_jsonl(ARTICLES_JSONL, article_rows)
    _write_jsonl(CHUNKS_JSONL, [{k: v for k, v in row.items() if k != "embedding"} for row in chunk_rows])

    if args.dry_run:
        print(f"dry run: {len(article_rows)} articles, {len(chunk_rows)} chunks (DB untouched)")
        return 0

    with load_db.connect(args.db_url) as conn:
        load_db.ensure_schema(conn)
        dim = load_db.embedding_dim(conn)
        if dim != embedder.spec.dim:
            sys.exit(
                f"DB embedding column is {dim}-dim but the model outputs {embedder.spec.dim}; "
                "run the matching model or migrate the schema and re-embed everything"
            )
        for meta, report, page_count in ingested:
            law_id = load_db.upsert_law(
                conn,
                meta,
                page_count=page_count,
                article_count=len(report.articles),
                preamble=report.preamble[:4000],
                warnings=report.warnings,
            )
            article_ids = load_db.insert_articles(
                conn, law_id, [r for r in article_rows if r["law_slug"] == meta.slug]
            )
            rows = [
                {
                    "chunk_key": c["id"],
                    "ordinal": i,
                    "page": c["page"],
                    "text": c["passage"],
                    "article_id": article_ids[c["article_number"]],
                    "embedding": c["embedding"],
                }
                for i, c in enumerate(x for x in chunk_rows if x["law_slug"] == meta.slug)
            ]
            load_db.insert_chunks(conn, law_id, rows)
        _print_summary(load_db.summary(conn))
    return 0


def _process_file(meta: catalog.LawMeta, args: argparse.Namespace) -> tuple[structure.StructureReport, int]:
    """Read pages (text layer first; OCR as fallback) and segment into articles.

    The OCR fallback fires on two signals: no articles at all, or a suspiciously low
    article density — the labour-code Arabic PDF, for example, extracts 23 headers across
    162 pages while the same text really has ~570 (the layer scrambles header lines). OCR
    is only attempted when tesseract is installed.
    """
    path = fetch.ensure_file(meta, RAW_DIR, verify_only=args.skip_fetch)
    ocr_lang = "ara" if meta.language == "ar" else "fra"
    pages = _read(path, ocr_lang)
    report = _try_segment(pages, meta.article_words)
    if (report is None or len(report.articles) < _expected_articles(len(pages))) and shutil.which("tesseract"):
        signal = "no articles" if report is None else f"only {len(report.articles)} articles in {len(pages)} pages"
        print(f"  {meta.slug}: {signal} in the text layer, falling back to OCR ({ocr_lang})")
        ocr_pages = _read(path, ocr_lang, force_ocr=True)
        ocr_report = _try_segment(ocr_pages, meta.article_words)
        if ocr_report is not None and (report is None or len(ocr_report.articles) > len(report.articles)):
            return ocr_report, len(ocr_pages)
        if ocr_report is not None and report is not None:
            report.warnings.append("OCR fallback produced fewer articles than the text layer")
    if report is None:
        raise structure.StructureError(
            f"{meta.slug}: no articles found in the text layer and OCR was unavailable or unhelpful"
        )
    if len(report.articles) < _expected_articles(len(pages)):
        report.warnings.append("low article density — text layer may be corrupted")
    return report, len(pages)


def _try_segment(pages: list[parse.Page], article_words: tuple[str, ...]) -> structure.StructureReport | None:
    try:
        return structure.segment(pages, article_words)
    except structure.StructureError:
        return None


def _expected_articles(page_count: int) -> int:
    """Minimum plausible article count for a law of this length (0.5 per page, floor 3)."""
    return max(3, int(0.5 * page_count))


def _read(path: Path, ocr_lang: str, force_ocr: bool = False) -> list[parse.Page]:
    return list(
        parse.read_pages(
            path,
            ocr_lang=ocr_lang if force_ocr else None,
            ocr_cache=RAW_DIR.parent / "ocr",
        )
    )


def _passage_text(meta: catalog.LawMeta, article: structure.ArticleDraft, text: str) -> str:
    """Embedding input carries the law + article context so vectors know what they describe."""
    if meta.language == "fr":
        title = meta.title_fr or meta.title_ar
        return f"{title} — Article {article.number}: {text}"
    return f"{meta.title_ar} — المادة {article.number}: {text}"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _print_summary(report: dict) -> None:
    print("\nLoaded into Postgres:")
    print(f"{'slug':34} {'domain':12} {'lang':5} {'articles':>9} {'pages':>6} {'chunks':>7}")
    for law in report["laws"]:
        print(
            f"{law['slug']:34} {law['domain']:12} {law['language']:5} "
            f"{law['articles']:>9} {law['pages']:>6} {law['chunks']:>7}"
        )
    totals = report["totals"]
    print(f"\ntotals: {totals['laws']} laws, {totals['articles']} articles, {totals['chunks']} chunks")


def show_summary(args: argparse.Namespace) -> int:
    with load_db.connect(args.db_url) as conn:
        _print_summary(load_db.summary(conn))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qanoun_pipeline", description=__doc__)
    parser.add_argument("--db-url", default=DEFAULT_DB, help="Postgres URL (or set QANOUN_DB_URL)")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest-all", help="fetch → parse → structure → chunk → embed → load")
    p_ingest.add_argument("--skip-fetch", action="store_true", help="never hit the network")
    p_ingest.add_argument("--domains", help="comma-separated domain filter")
    p_ingest.add_argument("--limit", type=int, help="only the first N catalog entries")
    p_ingest.add_argument("--chunk-size", type=int, default=chunk.DEFAULT_SIZE)
    p_ingest.add_argument("--chunk-overlap", type=int, default=chunk.DEFAULT_OVERLAP)
    p_ingest.add_argument("--fake-embed", action="store_true", help="hash-based embeddings (smoke test only)")
    p_ingest.add_argument("--dry-run", action="store_true", help="stop before touching the database")
    p_ingest.set_defaults(func=ingest_all)

    p_sum = sub.add_parser("summary", help="what is currently in the database")
    p_sum.set_defaults(func=show_summary)

    args = parser.parse_args(argv)
    if os.environ.get("QANOUN_DB_URL") and not any(a.startswith("--db-url") for a in (argv or [])):
        args.db_url = os.environ["QANOUN_DB_URL"]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
