"""Response model for POST /ingest."""
from pydantic import BaseModel


class IngestError(BaseModel):
    """One document that was not indexed, and why (no document text, only ids and reasons)."""

    doc_id: str | None
    reason: str


class IngestReport(BaseModel):
    """Counts of documents indexed (new or changed), skipped (unchanged) and failed, plus the errors."""

    indexed: int
    skipped: int
    failed: int
    errors: list[IngestError]
