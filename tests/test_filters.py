"""Tests for the shared filter. All records are FAKE."""
import pytest
from pydantic import ValidationError

from app.retrieval.filters import SearchFilters, apply_filters
from app.schemas.document import ChunkRecord


def rec(chunk_id: str, year: int | None, doc_type: str | None, category: str = "Roads and Transport") -> ChunkRecord:
    """Build a FAKE chunk record."""
    return ChunkRecord(chunk_id=chunk_id, doc_id="fake", chunk_index=0, title="FAKE", source_url="https://fake.example",
                       primary_category=category, locator_type="page", page_start=1, page_end=1, article=None,
                       text="FAKE", doc_type=doc_type, number=None, year=year, authority=None, status=None)


RECORDS = [rec("a", 2020, "Law"), rec("b", 2020, "Resolution"), rec("c", 2023, "Law"), rec("d", None, None)]


def ids(filters: SearchFilters) -> list[str]:
    """Return the chunk ids the filter allows."""
    return [r.chunk_id for r in apply_filters(RECORDS, filters)]


def test_year_filter() -> None:
    """AT-04: year filter returns only that year."""
    assert ids(SearchFilters(year=2020)) == ["a", "b"]


def test_type_filter_is_case_insensitive() -> None:
    """AT-04: type filter returns only that type."""
    assert ids(SearchFilters(doc_type="law")) == ["a", "c"]


def test_combined_filters_must_all_match() -> None:
    """AT-04: year AND type together."""
    assert ids(SearchFilters(year=2020, doc_type="Law")) == ["a"]


def test_no_match_returns_empty_list_not_error() -> None:
    """AT-04: a filter nothing satisfies gives an empty result."""
    assert ids(SearchFilters(year=1999)) == []


def test_chunks_with_missing_metadata_never_match_a_set_filter() -> None:
    """A null year/type must not slip through a filter that asks for a value."""
    assert "d" not in ids(SearchFilters(year=2020)) and "d" not in ids(SearchFilters(doc_type="Law"))


def test_category_boundary_is_enforced_even_with_no_filters() -> None:
    """RAG-03/AT-01: an out-of-category chunk is never returned, whatever the filters say."""
    records = RECORDS + [rec("traffic", 2020, "Law", category="Traffic")]
    assert "traffic" not in [r.chunk_id for r in apply_filters(records, SearchFilters())]
    assert "traffic" not in [r.chunk_id for r in apply_filters(records, SearchFilters(year=2020, doc_type="Law"))]


def test_invalid_year_is_rejected_by_the_schema() -> None:
    """AT-11: invalid filter values give a validation error, not odd behaviour."""
    with pytest.raises(ValidationError):
        SearchFilters(year=3000)
