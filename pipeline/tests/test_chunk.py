import pytest

from qanoun_pipeline.chunk import Chunk, chunk_article
from qanoun_pipeline.structure import ArticleDraft


def article(n_words: int, number: str = "7") -> ArticleDraft:
    return ArticleDraft(number, 1, " ".join(f"كلمة{i}" for i in range(n_words)), 3, 4)


def test_short_article_is_single_chunk():
    chunks = chunk_article("law", article(50))
    assert len(chunks) == 1
    assert chunks[0].id == "law#a7-c0"
    assert chunks[0].law_slug == "law"
    assert chunks[0].article_number == "7"


def test_long_article_is_chunked_with_overlap():
    chunks = chunk_article("law", article(400), size=180, overlap=40)
    assert len(chunks) >= 2
    # windows advance by size-overlap
    first = chunks[0].text.split()
    second = chunks[1].text.split()
    assert first[140:180] == second[0:40]


def test_chunk_ids_are_stable():
    assert chunk_article("law", article(400), 180, 40)[1].id == chunk_article(
        "law", article(400), 180, 40
    )[1].id


def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        chunk_article("law", article(10), size=50, overlap=50)


def test_as_dict_has_all_fields():
    d = chunk_article("law", article(5))[0].as_dict()
    assert set(d) == {"id", "law_slug", "article_number", "page", "text"}
    assert isinstance(Chunk(**d), Chunk)
