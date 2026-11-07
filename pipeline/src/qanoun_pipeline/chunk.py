"""Article texts → overlapping word-window chunks (ported from darija-rag).

Chunk ids are stable across re-ingestion ({law}#a{number}-c{i}): they key the embedding
cache, so unchanged articles are never re-embedded.
"""

from dataclasses import asdict, dataclass

from qanoun_pipeline.structure import ArticleDraft

DEFAULT_SIZE = 180  # words; most legal articles fit in one chunk
DEFAULT_OVERLAP = 40


@dataclass(frozen=True)
class Chunk:
    id: str
    law_slug: str
    article_number: str
    page: int  # page_start of the article, for reader deep-links
    text: str

    def as_dict(self) -> dict:
        return asdict(self)


def chunk_article(
    law_slug: str, article: ArticleDraft, size: int = DEFAULT_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("overlap must be >= 0 and smaller than size")
    words = article.text.split()
    step = size - overlap
    chunks = []
    for index, start in enumerate(range(0, len(words), step)):
        window = words[start : start + size]
        chunks.append(
            Chunk(
                f"{law_slug}#a{article.number}-c{index}",
                law_slug,
                article.number,
                article.page_start,
                " ".join(window),
            )
        )
        if start + size >= len(words):
            break
    return chunks
