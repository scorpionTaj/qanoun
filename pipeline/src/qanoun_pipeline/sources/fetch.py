"""Fetch the corpus from official sources (Ministry of Justice portal) with sha256 proof.

Catalog-driven: every entry that has a source_url is downloaded into data/raw/ if absent,
then verified against its catalog sha256. Files already on disk (like the ones carried over
from darija-rag) are only verified, never re-downloaded.
"""

import urllib.parse
from pathlib import Path

import httpx

from qanoun_pipeline.catalog import LawMeta, file_sha256


class FetchError(RuntimeError):
    pass


def upload_url(source_url: str) -> str:
    """Quote each path segment so Arabic filenames become valid URLs."""
    scheme, rest = source_url.split("://", 1)
    host, *segments = rest.split("/")
    quoted = "/".join(urllib.parse.quote(s) for s in segments)
    return f"{scheme}://{host}/{quoted}"


def ensure_file(meta: LawMeta, raw_dir: Path, *, verify_only: bool = False) -> Path:
    dest = raw_dir / meta.file
    if dest.exists():
        actual = file_sha256(dest)
        if meta.sha256 and actual != meta.sha256:
            raise FetchError(
                f"{meta.file}: sha256 mismatch (have {actual[:12]}…, catalog expects "
                f"{meta.sha256[:12]}…) — delete the file and re-fetch"
            )
        return dest
    if verify_only or not meta.source_url:
        raise FetchError(
            f"{meta.file} missing and no source to fetch from "
            f"({'verify-only run' if verify_only else 'no source_url in catalog'})"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", upload_url(meta.source_url), timeout=120, follow_redirects=True) as r:
        if r.status_code >= 400:
            raise FetchError(f"{meta.file}: HTTP {r.status_code} from {meta.source_url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with tmp.open("wb") as f:
            for block in r.iter_bytes(1 << 20):
                f.write(block)
        tmp.replace(dest)
    actual = file_sha256(dest)
    if meta.sha256 and actual != meta.sha256:
        dest.unlink()
        raise FetchError(f"{meta.file}: downloaded file failed sha256 verification")
    return dest


def ensure_corpus(laws: list[LawMeta], raw_dir: Path, *, verify_only: bool = False) -> list[Path]:
    return [ensure_file(law, raw_dir, verify_only=verify_only) for law in laws]
