"""Tests for ingest_all with FAKE manifest, FAKE pdf files and a fake parser (no real documents are used)."""
import csv
import sqlite3
from pathlib import Path

from app.config import Settings
from app.ingestion import pipeline
from app.ingestion.pipeline import ingest_all
from app.schemas.document import ParsedPage

COLUMNS = ["doc_id", "file_name", "title", "source_url", "content_url", "primary_category", "language",
           "retrieval_date", "doc_type", "number", "year", "authority", "status", "issue_date", "notes"]


def fake_row(doc_id: str, **changes: str) -> dict[str, str]:
    """Build a FAKE manifest row."""
    row = {c: "" for c in COLUMNS}
    row.update(doc_id=doc_id, file_name=f"{doc_id}.pdf", title=f"FAKE {doc_id}", source_url="https://fake.example/a",
              content_url="https://fake.example/a.pdf", primary_category="Roads and Transport", language="English",
              retrieval_date="2000-01-01")
    return {**row, **changes}


def setup(tmp_path: Path, rows: list[dict[str, str]], monkeypatch, fail_for: str | None = None):
    """Create FAKE files and manifest; replace the PDF parser with one returning FAKE pages (or failing for one file)."""
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    for r in rows:
        (raw / r["file_name"]).write_bytes(b"%PDF-FAKE " + r["doc_id"].encode())
    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    def fake_parse(path: Path) -> list[ParsedPage]:
        if fail_for and fail_for in path.name:
            raise RuntimeError("FAKE corrupt pdf")
        return [ParsedPage(page_number=1, text="Article (1)\nFAKE rule one.\nArticle (2)\nFAKE rule two.")]

    monkeypatch.setattr(pipeline, "parse_pdf", fake_parse)
    return manifest, raw, Settings(_env_file=None, db_path=str(tmp_path / "t.sqlite"))


def count(settings: Settings) -> int:
    """Count stored chunks."""
    return sqlite3.connect(settings.db_path).execute("SELECT COUNT(*) FROM chunks").fetchone()[0]


def test_second_run_skips_unchanged_documents_and_creates_no_duplicates(tmp_path, monkeypatch) -> None:
    """AT-02/DATA-05: re-ingesting unchanged inputs changes nothing."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a"), fake_row("b")], monkeypatch)
    first = ingest_all(settings, manifest, raw)
    rows_after_first = count(settings)
    second = ingest_all(settings, manifest, raw)
    assert (first.indexed, first.skipped, first.failed) == (2, 0, 0)
    assert (second.indexed, second.skipped, second.failed) == (0, 2, 0)
    assert count(settings) == rows_after_first == 4  # the fake text starts with Article (1): 2 chunks per document, no opening chunk


def test_changed_file_is_reindexed(tmp_path, monkeypatch) -> None:
    """A changed PDF must be re-ingested, not skipped."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a")], monkeypatch)
    ingest_all(settings, manifest, raw)
    (raw / "a.pdf").write_bytes(b"%PDF-FAKE changed")
    again = ingest_all(settings, manifest, raw)
    assert (again.indexed, again.skipped) == (1, 0)


def test_changing_chunk_settings_triggers_reindex(tmp_path, monkeypatch) -> None:
    """The fingerprint includes chunk size/overlap, so new settings rebuild the chunks."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a")], monkeypatch)
    ingest_all(settings, manifest, raw)
    new = settings.model_copy(update={"chunk_size": 500})
    assert ingest_all(new, manifest, raw).indexed == 1


def test_failing_document_is_reported_and_others_still_load(tmp_path, monkeypatch) -> None:
    """DATA-02: a parse failure is logged in the report; it never silently disappears or stops the run."""
    manifest, raw, settings = setup(tmp_path, [fake_row("good"), fake_row("bad")], monkeypatch, fail_for="bad")
    report = ingest_all(settings, manifest, raw)
    assert (report.indexed, report.failed) == (1, 1)
    assert report.errors[0].doc_id == "bad" and "RuntimeError" in report.errors[0].reason


def test_out_of_category_row_is_counted_failed_and_never_indexed(tmp_path, monkeypatch) -> None:
    """AT-01: a deliberately out-of-category record is excluded and appears in the errors."""
    manifest, raw, settings = setup(tmp_path, [fake_row("ok"), fake_row("traffic", primary_category="Traffic")], monkeypatch)
    report = ingest_all(settings, manifest, raw)
    assert report.indexed == 1 and report.failed == 1
    ids = {r[0] for r in sqlite3.connect(settings.db_path).execute("SELECT DISTINCT doc_id FROM chunks")}
    assert ids == {"ok"}


def test_document_removed_from_manifest_is_purged_from_the_index(tmp_path, monkeypatch) -> None:
    """The corpus boundary also holds inside the index: unlisted documents must not stay searchable."""
    manifest, raw, settings = setup(tmp_path, [fake_row("a"), fake_row("b")], monkeypatch)
    ingest_all(settings, manifest, raw)
    manifest2, _, _ = setup(tmp_path, [fake_row("a")], monkeypatch)  # rewrite manifest with only "a"
    ingest_all(settings, manifest2, raw)
    ids = {r[0] for r in sqlite3.connect(settings.db_path).execute("SELECT DISTINCT doc_id FROM chunks")}
    assert ids == {"a"}
