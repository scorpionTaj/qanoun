"""Turn raw PDFs/text files into page-level records (display text kept verbatim)."""

import os
import shutil
import subprocess
import unicodedata
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class Page:
    doc: str
    page: int  # 1-based, matches what a reader sees in the PDF viewer
    text: str


def read_pages(
    path: Path, ocr_lang: str | None = None, ocr_cache: Path | None = None
) -> Iterator[Page]:
    """Yield display-text pages. PDFs whose text layer is broken need OCR (ocr_lang set)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf" and ocr_lang:
        texts = ocr_pdf(path, ocr_lang, ocr_cache or path.parent / "ocr")
    elif suffix == ".pdf":
        with pymupdf.open(path) as pdf:
            # Content-stream order: sort=True reorders by position and reverses Arabic words.
            texts = [pdf_page.get_text() for pdf_page in pdf]
    elif suffix == ".txt":
        # Form feeds separate pages, so plain-text exports keep page citations.
        texts = path.read_text(encoding="utf-8").split("\f")
    else:
        raise ValueError(f"unsupported file type: {path}")
    for number, text in enumerate(texts, start=1):
        if text.strip():
            yield Page(path.name, number, clean(text))


def clean(text: str) -> str:
    """Keep original spelling for display/citation; only fold presentation forms and whitespace.

    Line breaks are preserved: article-header detection segments on lines, and headers
    ("المادة 12") must still start a line after cleaning.
    """
    text = unicodedata.normalize("NFKC", text)
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


def ocr_pdf(path: Path, lang: str, cache_dir: Path, dpi: int = 300) -> list[str]:
    """OCR for PDFs whose embedded text layer is unusable (common for Arabic: reversed words,
    swapped lam-alef ligatures, scrambled letters).

    Calls the tesseract CLI directly: PyMuPDF's built-in OCR text page reverses some
    right-to-left lines. Results are cached as one form-feed separated text file per PDF,
    because a full OCR pass takes minutes and re-ingestion should not repeat it.
    """
    cache = cache_dir / f"{path.name}.{lang}.txt"
    if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
        return cache.read_text(encoding="utf-8").split("\f")
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract is not installed (brew install tesseract tesseract-lang)")

    with pymupdf.open(path) as pdf:
        images = [page.get_pixmap(dpi=dpi).tobytes("png") for page in pdf]
    workers = max(1, (os.cpu_count() or 2) - 1)
    with ThreadPoolExecutor(workers) as pool:
        texts = list(pool.map(lambda image: _tesseract(image, lang), images))

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".part")
    tmp.write_text("\f".join(texts), encoding="utf-8")
    tmp.replace(cache)
    return texts


def _tesseract(png: bytes, lang: str) -> str:
    result = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", lang],
        input=png,
        capture_output=True,
        check=True,
        # One thread per process; parallelism comes from the pool.
        env={**os.environ, "OMP_THREAD_LIMIT": "1"},
    )
    return result.stdout.decode("utf-8")
