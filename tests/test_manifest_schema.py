"""Tests for ManifestRecord. All rows are FAKE test data, kept separate from the real corpus."""
import pytest
from pydantic import ValidationError

from app.schemas.manifest import ManifestRecord

FAKE_ROW = {
    "doc_id": "fake-001", "file_name": "FAKE.pdf", "title": "FAKE Test Document",
    "source_url": "https://fake.example/page", "content_url": "https://fake.example/file.pdf",
    "primary_category": "Roads and Transport", "language": "English", "retrieval_date": "2000-01-01",
    "doc_type": "Law", "number": "1", "year": "2000", "authority": "FAKE Authority",
    "status": "In Force", "issue_date": "1 Jan 2000", "notes": "",
}


def test_valid_row_is_accepted_and_blank_notes_become_null() -> None:
    """Protects the happy path and the blank-to-null rule (DATA-04)."""
    record = ManifestRecord(**FAKE_ROW)
    assert record.year == 2000
    assert record.notes is None


def test_out_of_category_record_is_rejected() -> None:
    """AT-01: a deliberately out-of-category record must not get into the corpus."""
    with pytest.raises(ValidationError) as error:
        ManifestRecord(**{**FAKE_ROW, "primary_category": "Traffic"})
    assert error.value.errors()[0]["loc"] == ("primary_category",)


@pytest.mark.parametrize("field", ["doc_id", "file_name", "title", "source_url", "content_url", "retrieval_date"])
def test_missing_required_field_is_rejected(field: str) -> None:
    """Protects the rule that required fields can't be empty."""
    with pytest.raises(ValidationError):
        ManifestRecord(**{**FAKE_ROW, field: ""})


def test_blank_optional_fields_are_accepted_as_null() -> None:
    """Protects DATA-04: unavailable metadata is null, not a rejection."""
    record = ManifestRecord(**{**FAKE_ROW, "number": "", "year": "", "status": ""})
    assert record.number is None and record.year is None and record.status is None
