"""Load and check the manifest; excluded rows are reported and logged, never silently dropped (DATA-01/02, AT-01)."""
import csv
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas.manifest import ManifestRecord, Rejection

logger = logging.getLogger(__name__)


def check_row(row: dict[str, str], raw_dir: Path, seen: set[str]) -> tuple[ManifestRecord | None, list[str]]:
    """Return the validated record, or None plus every reason the row is excluded."""
    try:
        record = ManifestRecord(**row)
    except ValidationError as exc:
        return None, [f"{e['loc'][0]}: {e['msg']}" for e in exc.errors()]
    reasons = []
    pdf = raw_dir / record.file_name
    if not pdf.is_file() or pdf.stat().st_size == 0:  # the schema cannot know about the disk
        reasons.append("file_name: PDF missing or empty in raw folder")
    if record.doc_id in seen:  # IDs must stay stable, so we flag duplicates instead of renaming them
        reasons.append("doc_id: duplicate")
    return (None, reasons) if reasons else (record, [])


def load_manifest(manifest_path: Path, raw_dir: Path) -> tuple[list[ManifestRecord], list[Rejection]]:
    """Check every row and return (accepted, rejected); one bad row never blocks the rest."""
    accepted: list[ManifestRecord] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()
    with open(manifest_path, encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):  # line 1 is the header
            record, reasons = check_row(row, raw_dir, seen)
            if record:
                seen.add(record.doc_id)
                accepted.append(record)
            else:
                rejected.append(Rejection(line=line, doc_id=row.get("doc_id") or None, reasons=reasons))
                logger.warning("manifest line %s (doc_id=%s) excluded: %s", line, row.get("doc_id"), reasons)
    return accepted, rejected
