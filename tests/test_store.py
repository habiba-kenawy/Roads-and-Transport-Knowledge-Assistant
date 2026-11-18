"""Tests for chunk IDs and the SQLite store. All data is FAKE and lives in a temp database."""
from pathlib import Path

from app.ingestion.store import build_records, connect, make_chunk_id, replace_document_chunks
from app.schemas.document import Chunk
from app.schemas.manifest import ManifestRecord

DOC = ManifestRecord(doc_id="fake-1", file_name="fake.pdf", title="FAKE Title", source_url="https://fake.example/a",
                     content_url="https://fake.example/a.pdf", primary_category="Roads and Transport",
                     language="English", retrieval_date="2000-01-01", doc_type="", number="", year="", authority="",
                     status="", issue_date="", notes="")


def fake_chunks(*texts: str) -> list[Chunk]:
    """Build FAKE chunks on page 1."""
    return [Chunk(article=f"Article ({i + 1})", text=t, page_start=1, page_end=1) for i, t in enumerate(texts)]


def test_chunk_id_is_stable_and_changes_with_text_or_position() -> None:
    """DATA-05: same input, same id; different text or position, different id."""
    assert make_chunk_id("d", 0, "abc") == make_chunk_id("d", 0, "abc")
    assert make_chunk_id("d", 0, "abc") != make_chunk_id("d", 0, "abd")
    assert make_chunk_id("d", 0, "abc") != make_chunk_id("d", 1, "abc")


def test_missing_metadata_is_stored_as_null_and_identical_texts_get_distinct_ids() -> None:
    """DATA-04: unknown type/number/year/authority/status are None; repeated texts still get unique ids."""
    records = build_records(DOC, fake_chunks("same", "same"))
    assert records[0].year is None and records[0].status is None and records[0].authority is None
    assert records[0].chunk_id != records[1].chunk_id


def test_reingesting_unchanged_document_creates_no_duplicates(tmp_path: Path) -> None:
    """DATA-05/AT-02: running the same ingestion twice leaves the same rows."""
    conn = connect(str(tmp_path / "t.sqlite"))
    records = build_records(DOC, fake_chunks("one", "two", "three"))
    replace_document_chunks(conn, "fake-1", records, "fp")
    replace_document_chunks(conn, "fake-1", records, "fp")
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 3


def test_changed_document_replaces_old_chunks_without_leftovers(tmp_path: Path) -> None:
    """Protects against stale chunks: a shorter, edited document must not keep its old rows."""
    conn = connect(str(tmp_path / "t.sqlite"))
    replace_document_chunks(conn, "fake-1", build_records(DOC, fake_chunks("one", "two", "three")), "fp")
    replace_document_chunks(conn, "fake-1", build_records(DOC, fake_chunks("one edited")), "fp")
    rows = conn.execute("SELECT text FROM chunks").fetchall()
    assert rows == [("one edited",)]


def test_other_documents_are_untouched_when_one_is_replaced(tmp_path: Path) -> None:
    """Protects the per-document replace: it only deletes the given doc_id."""
    conn = connect(str(tmp_path / "t.sqlite"))
    other = DOC.model_copy(update={"doc_id": "fake-2"})
    replace_document_chunks(conn, "fake-1", build_records(DOC, fake_chunks("a")), "fp")
    replace_document_chunks(conn, "fake-2", build_records(other, fake_chunks("b")), "fp")
    replace_document_chunks(conn, "fake-1", build_records(DOC, fake_chunks("a2")), "fp")
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id='fake-2'").fetchone()[0] == 1
