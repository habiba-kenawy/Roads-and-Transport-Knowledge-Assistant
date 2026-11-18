"""Schemas for parsed document content."""
from pydantic import BaseModel


class Chunk(BaseModel):
    """One searchable piece of a document; page_start/page_end give the locator, article is None for the opening text."""

    article: str | None
    text: str
    page_start: int
    page_end: int


class ChunkRecord(BaseModel):
    """One stored chunk: text, stable id, document metadata and locator (DATA-04). Unknown metadata is None."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    title: str
    source_url: str
    primary_category: str
    locator_type: str  # "page" for PDFs
    page_start: int
    page_end: int
    article: str | None
    text: str
    doc_type: str | None
    number: str | None
    year: int | None
    authority: str | None
    status: str | None


class ParsedPage(BaseModel):
    """Text of one PDF page; page_number is 1-based like a PDF viewer, so citations match what readers see."""

    page_number: int
    text: str
