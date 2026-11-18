"""Metadata filters shared by every search mode; the corpus boundary is enforced here, in code (RAG-03)."""
from pydantic import BaseModel, Field

from app.schemas.document import ChunkRecord

CATEGORY = "Roads and Transport"  # fixed: not a request option, so no caller can widen the corpus


class SearchFilters(BaseModel):
    """Optional metadata filters a caller may send; None means 'no restriction on this field'."""

    year: int | None = Field(default=None, ge=1900, le=2100)
    doc_type: str | None = Field(default=None, min_length=1)


def matches(record: ChunkRecord, filters: SearchFilters) -> bool:
    """True only if the chunk is in the corpus AND satisfies every filter that was set."""
    if record.primary_category != CATEGORY:
        return False
    if filters.year is not None and record.year != filters.year:
        return False
    if filters.doc_type is not None and (record.doc_type or "").lower() != filters.doc_type.lower():
        return False
    return True


def apply_filters(records: list[ChunkRecord], filters: SearchFilters) -> list[ChunkRecord]:
    """Return the allowed chunks; each search mode must rank only these, before choosing its final candidates."""
    return [r for r in records if matches(r, filters)]
