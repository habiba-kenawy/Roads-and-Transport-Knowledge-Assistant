"""Download only the PDFs listed in data/manifest.csv, with retries, and log every outcome (DATA-02)."""
import csv
import sys
import time
from datetime import date
from pathlib import Path

import requests

HEADERS = {"User-Agent": "roads-transport-assignment/1.0"}
ATTEMPTS = 3
PAUSE_BETWEEN_FILES = 1.0  # be polite: one request at a time
TIMEOUT = 60


def fetch(url: str) -> tuple[bytes | None, int, str]:
    """Try the URL up to ATTEMPTS times with growing waits; return (bytes or None, attempts used, last error)."""
    error = ""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and r.content.startswith(b"%PDF"):
                return r.content, attempt, ""
            error = f"HTTP {r.status_code}, not a PDF" if r.status_code == 200 else f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            error = type(exc).__name__
        if attempt < ATTEMPTS:
            time.sleep(2 * attempt)
    return None, ATTEMPTS, error


def main(manifest: str, raw_dir: str, log_path: str) -> None:
    """Download each manifest file not already on disk and write a per-file status log."""
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(manifest, encoding="utf-8-sig")))
    log = []
    for row in rows:
        target = Path(raw_dir) / row["file_name"]
        if target.exists() and target.stat().st_size > 0:
            if not row["retrieval_date"]:  # file predates the date column: use when it was written to disk
                row["retrieval_date"] = date.fromtimestamp(target.stat().st_mtime).isoformat()
            log.append({"doc_id": row["doc_id"], "file_name": row["file_name"], "status": "skipped_exists",
                        "attempts": 0, "error": "", "bytes": target.stat().st_size})
            continue
        data, attempts, error = fetch(row["content_url"])
        if data:
            target.write_bytes(data)
            row["retrieval_date"] = date.today().isoformat()
        log.append({"doc_id": row["doc_id"], "file_name": row["file_name"],
                    "status": "downloaded" if data else "failed", "attempts": attempts,
                    "error": error, "bytes": len(data) if data else 0})
        print(log[-1]["status"], row["doc_id"], error)
        time.sleep(PAUSE_BETWEEN_FILES)
    with open(manifest, "w", newline="", encoding="utf-8-sig") as f:  # persist the retrieval dates
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doc_id", "file_name", "status", "attempts", "error", "bytes"])
        w.writeheader()
        w.writerows(log)
    counts = {s: sum(1 for x in log if x["status"] == s) for s in ("downloaded", "skipped_exists", "failed")}
    print("summary:", counts)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
