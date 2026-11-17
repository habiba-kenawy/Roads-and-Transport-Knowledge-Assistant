"""Write each accepted document's parsed pages to data/parsed/<doc_id>.txt so a human can read them (viewing aid only)."""
import logging
from pathlib import Path

from app.ingestion.manifest import load_manifest
from app.ingestion.pdf_parser import parse_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("dump_parsed")


def main(manifest: Path = Path("data/manifest.csv"), raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/parsed")) -> None:
    """Parse every accepted manifest document; a failing file is logged and the rest continue."""
    out_dir.mkdir(parents=True, exist_ok=True)
    accepted, _ = load_manifest(manifest, raw_dir)
    done, failed = 0, []
    for record in accepted:
        try:
            pages = parse_pdf(raw_dir / record.file_name)
        except Exception as exc:  # a corrupt PDF must not stop the other documents
            logger.error("parse failed doc_id=%s error=%s", record.doc_id, type(exc).__name__)
            failed.append(record.doc_id)
            continue
        body = "\n".join(f"=== PAGE {p.page_number} ===\n{p.text}" for p in pages)
        (out_dir / f"{record.doc_id}.txt").write_text(f"{record.title}\n\n{body}\n", encoding="utf-8")
        done += 1
    print(f"parsed files written: {done} | failed: {failed}")


if __name__ == "__main__":
    main()
