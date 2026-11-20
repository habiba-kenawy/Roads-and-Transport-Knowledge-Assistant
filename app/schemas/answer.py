"""Schemas for the grounded answer (RAG-05, 8.2)."""
from pydantic import BaseModel


class Statement(BaseModel):
    """One sentence the model wants in the answer, with its source chunk and a short exact quote from that chunk."""

    text: str
    chunk_id: str
    quote: str


class AnswerDraft(BaseModel):
    """The model's structured output: whether the evidence suffices, and the sentences if it does."""

    evidence_is_sufficient: bool
    statements: list[Statement]


class Citation(BaseModel):
    """A verified source: built from stored chunk data (never from model text), so it always resolves to a real chunk."""

    document_id: str
    chunk_id: str
    title: str
    source_url: str
    locator_type: str
    locator: str  # e.g. "p. 2" or "pp. 1-2"
