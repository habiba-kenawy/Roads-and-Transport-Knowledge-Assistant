"""Write each accepted document's pages to data/parsed/ (raw parse) and data/parsed_clean/ (after cleaning) for humans to read."""
import logging
from pathlib import Path

from app.ingestion.cleaner import clean_pages
from app.ingestion.manifest import load_manifest
from app.ingestion.pdf_parser import parse_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("dump_parsed")


def main(manifest: Path = Path("data/manifest.csv"), raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/parsed"), clean_dir: Path = Path("data/parsed_clean")) -> None:
    """Parse every accepted manifest document; a failing file is logged and the rest continue."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    accepted, _ = load_manifest(manifest, raw_dir)
    done, failed = 0, []
    for record in accepted:
        try:
            pages = parse_pdf(raw_dir / record.file_name)
        except Exception as exc:  # a corrupt PDF must not stop the other documents
            logger.error("parse failed doc_id=%s error=%s", record.doc_id, type(exc).__name__)
            failed.append(record.doc_id)
            continue
        for folder, version in ((out_dir, pages), (clean_dir, clean_pages(pages))):
            body = "\n".join(f"=== PAGE {p.page_number} ===\n{p.text}" for p in version)
            (folder / f"{record.doc_id}.txt").write_text(f"{record.title}\n\n{body}\n", encoding="utf-8")
        done += 1
    print(f"parsed files written: {done} | failed: {failed}")


if __name__ == "__main__":
    main()
