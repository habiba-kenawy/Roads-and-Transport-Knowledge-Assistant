"""Tests for parse_pdf using a FAKE reader, so no real PDF (git-ignored) is needed."""
from pathlib import Path

from app.ingestion import pdf_parser


class FakePage:
    """FAKE page whose extract_text returns a preset value (may be None, like pypdf for empty pages)."""

    def __init__(self, text: str | None) -> None:
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class FakeReader:
    """FAKE PdfReader with three pages; the middle one has no extractable text."""

    def __init__(self, path: Path) -> None:
        self.pages = [FakePage("FAKE first"), FakePage(None), FakePage("FAKE third")]


def test_pages_are_numbered_from_one_and_missing_text_becomes_empty(monkeypatch) -> None:
    """Protects the locator rule: page numbers match a PDF viewer, and no page text is ever None."""
    monkeypatch.setattr(pdf_parser, "PdfReader", FakeReader)
    pages = pdf_parser.parse_pdf(Path("FAKE.pdf"))
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert [p.text for p in pages] == ["FAKE first", "", "FAKE third"]
