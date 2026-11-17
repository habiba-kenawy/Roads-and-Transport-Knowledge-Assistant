"""Tests for load_manifest using a FAKE manifest and FAKE files in a temp folder (never the real corpus)."""
import csv
import logging
from pathlib import Path

from app.ingestion.manifest import load_manifest

COLUMNS = ["doc_id", "file_name", "title", "source_url", "content_url", "primary_category", "language",
           "retrieval_date", "doc_type", "number", "year", "authority", "status", "issue_date", "notes"]


def fake_row(doc_id: str, **changes: str) -> dict[str, str]:
    """Build a FAKE manifest row; each test breaks exactly one thing."""
    row = {"doc_id": doc_id, "file_name": f"{doc_id}.pdf", "title": f"FAKE title {doc_id}",
           "source_url": "https://fake.example/a", "content_url": "https://fake.example/a.pdf",
           "primary_category": "Roads and Transport", "language": "English", "retrieval_date": "2000-01-01",
           "doc_type": "", "number": "", "year": "", "authority": "", "status": "", "issue_date": "", "notes": ""}
    return {**row, **changes}


def write_fake_manifest(tmp_path: Path, rows: list[dict[str, str]], existing_pdfs: list[str]) -> tuple[Path, Path]:
    """Write a FAKE manifest CSV and FAKE (non-empty) PDF files into a temp folder."""
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in existing_pdfs:
        (raw / name).write_bytes(b"%PDF-FAKE")
    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return manifest, raw


def test_each_bad_row_is_rejected_with_a_reason_and_good_rows_still_load(tmp_path: Path) -> None:
    """AT-01/DATA-02: out-of-category, missing PDF, duplicate id and empty title are excluded, not silent."""
    rows = [
        fake_row("good-1"),
        fake_row("out-of-category", primary_category="Traffic"),
        fake_row("no-pdf"),
        fake_row("good-1", file_name="good-1.pdf"),  # duplicate id
        fake_row("no-title", title=""),
        fake_row("good-2"),
    ]
    manifest, raw = write_fake_manifest(tmp_path, rows, ["good-1.pdf", "out-of-category.pdf", "no-title.pdf", "good-2.pdf"])
    accepted, rejected = load_manifest(manifest, raw)
    assert [r.doc_id for r in accepted] == ["good-1", "good-2"]
    reasons = {r.doc_id: " ".join(r.reasons) for r in rejected}
    assert "primary_category" in reasons["out-of-category"]
    assert "PDF missing" in reasons["no-pdf"]
    assert "duplicate" in reasons["good-1"]
    assert "title" in reasons["no-title"]
    assert [r.line for r in rejected] == [3, 4, 5, 6]  # CSV line numbers, header is line 1


def test_rejections_are_logged(tmp_path: Path, caplog) -> None:
    """DATA-02: every exclusion produces a log line (no silent omission)."""
    manifest, raw = write_fake_manifest(tmp_path, [fake_row("out-of-category", primary_category="Traffic")], ["out-of-category.pdf"])
    with caplog.at_level(logging.WARNING):
        load_manifest(manifest, raw)
    assert "out-of-category" in caplog.text and "excluded" in caplog.text


def test_empty_pdf_is_rejected(tmp_path: Path) -> None:
    """Protects against a failed download leaving a zero-byte file."""
    manifest, raw = write_fake_manifest(tmp_path, [fake_row("empty")], [])
    (raw / "empty.pdf").write_bytes(b"")
    accepted, rejected = load_manifest(manifest, raw)
    assert accepted == [] and "PDF missing or empty" in rejected[0].reasons[0]
