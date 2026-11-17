"""Parse a text-based PDF into text per page (DATA-02)."""
from pathlib import Path

from pypdf import PdfReader

from app.schemas.document import ParsedPage


def parse_pdf(path: Path) -> list[ParsedPage]:
    """Return one ParsedPage per page, keeping page numbers because citations need a locator (DATA-04)."""
    reader = PdfReader(path)
    return [
        ParsedPage(page_number=number, text=page.extract_text() or "")  # a page with no text becomes ""
        for number, page in enumerate(reader.pages, start=1)  # start=1: PDF viewers count from 1
    ]
