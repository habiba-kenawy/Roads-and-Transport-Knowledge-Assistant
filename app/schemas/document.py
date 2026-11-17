"""Schemas for parsed document content."""
from pydantic import BaseModel


class ParsedPage(BaseModel):
    """Text of one PDF page; page_number is 1-based like a PDF viewer, so citations match what readers see."""

    page_number: int
    text: str
