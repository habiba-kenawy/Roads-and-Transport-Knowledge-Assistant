"""Schemas for parsed document content."""
from pydantic import BaseModel


class Chunk(BaseModel):
    """One searchable piece of a document; page_start/page_end give the locator, article is None for the opening text."""

    article: str | None
    text: str
    page_start: int
    page_end: int


class ParsedPage(BaseModel):
    """Text of one PDF page; page_number is 1-based like a PDF viewer, so citations match what readers see."""

    page_number: int
    text: str
