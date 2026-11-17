"""Schema for one manifest row; enforces the Roads and Transport corpus boundary in code (DATA-01, AT-01)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Rejection(BaseModel):
    """One excluded manifest row and why, so exclusions are never silent (DATA-02)."""

    line: int  # CSV line number, header is line 1
    doc_id: str | None
    reasons: list[str]


class ManifestRecord(BaseModel):
    """One approved document; any row that breaks a rule is rejected with a reason."""

    model_config = ConfigDict(str_strip_whitespace=True)

    doc_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    content_url: str = Field(min_length=1)
    primary_category: Literal["Roads and Transport"]  # anything else is refused
    language: str = Field(min_length=1)
    retrieval_date: str = Field(min_length=1)
    doc_type: str | None = None
    number: str | None = None
    year: int | None = None
    authority: str | None = None
    status: str | None = None
    issue_date: str | None = None
    notes: str | None = None

    @field_validator("doc_type", "number", "year", "authority", "status", "issue_date", "notes", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        """Turn empty CSV cells into null, since unavailable metadata must be null (DATA-04)."""
        return None if isinstance(value, str) and not value.strip() else value
