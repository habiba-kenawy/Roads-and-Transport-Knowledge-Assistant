"""Tests for split_articles. All text is FAKE; it only mimics the structure seen in the real documents."""
import pytest

from app.ingestion.chunker import split_articles
from app.schemas.document import ParsedPage


def split(*texts: str, size: int = 1000, overlap: int = 150):
    """Build FAKE pages numbered from 1 and split them."""
    pages = [ParsedPage(page_number=i, text=t) for i, t in enumerate(texts, start=1)]
    return split_articles(pages, chunk_size=size, chunk_overlap=overlap)


def test_preamble_and_each_article_become_separate_chunks() -> None:
    """DATA-03: boundaries at Article headings are preserved; text before Article 1 is its own chunk."""
    chunks = split("FAKE Law No. 1\nDo hereby issue.\nArticle (1)\nFAKE rule one.\nArticle (2)\nFAKE rule two.")
    assert [c.article for c in chunks] == [None, "Article (1)", "Article (2)"]
    assert chunks[1].text == "Article (1)\nFAKE rule one."


def test_article_crossing_a_page_break_reports_both_pages() -> None:
    """DATA-04: the locator keeps page_start and page_end so a citation can say pp. 1-2."""
    chunks = split("Article (1)\nFAKE start of a long rule", "that continues here.\nArticle (2)\nFAKE next.")
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)
    assert (chunks[1].page_start, chunks[1].page_end) == (2, 2)


def test_mid_sentence_article_reference_is_not_a_heading() -> None:
    """Real bug found on dlp-1941: 'Article (6) of this Resolution...' starting a line is not a heading."""
    chunks = split("Article (1)\nFAKE: as specified in\nArticle (6) of this Resolution and more.\nArticle (2)\nFAKE.")
    assert [c.article for c in chunks] == ["Article (1)", "Article (2)"]


def test_document_without_articles_is_one_chunk() -> None:
    """Protects against losing text when no Article heading exists."""
    chunks = split("FAKE plain text with no headings.")
    assert len(chunks) == 1 and chunks[0].article is None


def test_repeated_article_number_keeps_both_chunks() -> None:
    """Amending resolutions quote replacement articles, so the same label can legitimately appear twice."""
    chunks = split("Article (1)\nFAKE amendment.\nArticle (1)\nFAKE quoted replacement.")
    assert [c.article for c in chunks] == ["Article (1)", "Article (1)"]


def test_long_article_is_split_within_size_and_keeps_label_and_pages() -> None:
    """DATA-03: an article longer than chunk_size is cut; every piece stays under the limit and keeps its article."""
    body = "\n".join(f"FAKE sentence number {i} about nothing real." for i in range(40))
    chunks = split("Article (1)\n" + body[: len(body) // 2], body[len(body) // 2:] + "\nArticle (2)\nFAKE short.", size=200, overlap=40)
    long_pieces = [c for c in chunks if c.article == "Article (1)"]
    assert len(long_pieces) > 3
    assert all(len(c.text) <= 200 for c in chunks)
    assert long_pieces[0].page_start == 1 and long_pieces[-1].page_end == 2
    assert [c.article for c in chunks][-1] == "Article (2)"


def test_neighbouring_pieces_overlap() -> None:
    """Protects the overlap setting: the end of one piece is repeated at the start of the next."""
    body = "\n".join(f"FAKE line {i:02d} with some filler words." for i in range(30))
    pieces = split("Article (1)\n" + body, size=200, overlap=60)
    assert any(a.text.splitlines()[-1] in b.text for a, b in zip(pieces, pieces[1:]))


def test_overlap_larger_than_size_is_refused() -> None:
    """Protects against a misconfigured .env: the splitter must fail loudly, not produce odd chunks."""
    with pytest.raises(ValueError):
        split("Article (1)\nFAKE.", size=100, overlap=200)
