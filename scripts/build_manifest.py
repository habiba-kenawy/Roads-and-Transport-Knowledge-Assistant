"""Build data/manifest.csv from the portal results page the user saved after applying the category filter."""
import csv
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

CATEGORY = "Roads and Transport"  # the filter the user applied on the portal; not a per-item field
COLUMNS = ["doc_id", "file_name", "title", "source_url", "content_url", "primary_category", "language",
           "retrieval_date", "doc_type", "number", "year", "authority", "status", "issue_date", "notes"]


def field(li, label: str) -> str:
    """Return the value shown under a labelled box (e.g. 'Type'), or '' if the item lacks it."""
    for h3 in li.find_all("h3"):
        if h3.get_text(strip=True) == label:
            h4 = h3.find_next_sibling("h4")
            return h4.get_text(strip=True) if h4 else ""
    return ""


def link(li, css: str) -> str:
    """Return the href inside a result-icon cell, or '' if absent."""
    a = li.select_one(css)
    return a["href"].strip() if a and a.has_attr("href") else ""


def parse_item(li) -> dict[str, str]:
    """Turn one result <li> into one manifest row; blanks mean 'not available', never guessed."""
    title = li.select_one(".title").get_text(" ", strip=True)
    pdf = link(li, ".viewPdf a")
    issue_date = field(li, "Date of Issuance")
    number = re.search(r"No\.\s*\((\d+)\)", title)
    year = re.search(r"(\d{4})$", issue_date)
    return {
        "doc_id": f"dlp-{li['data-id']}",  # portal's own item id keeps IDs stable across rebuilds
        "file_name": Path(unquote(urlparse(pdf).path)).name,
        "title": title,
        "source_url": link(li, ".html a"),
        "content_url": pdf,
        "primary_category": CATEGORY,
        "language": "English",
        "retrieval_date": "",  # filled by download_pdfs.py when the file is actually retrieved
        "doc_type": field(li, "Type"),
        "number": number.group(1) if number else "",
        "year": year.group(1) if year else "",
        "authority": field(li, "Issuing Authority"),
        "status": field(li, "Status"),
        "issue_date": issue_date,
        "notes": "",
    }


def main(html_path: str, out_path: str) -> None:
    """Read the saved page, write the manifest, and fail loudly on duplicates or missing PDF links."""
    soup = BeautifulSoup(Path(html_path).read_text(encoding="utf-8"), "html.parser")
    rows = [parse_item(li) for li in soup.select(".result-listing ul > li")]
    ids = [r["doc_id"] for r in rows]
    names = [r["file_name"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate doc_id"
    assert len(names) == len(set(names)), "duplicate file_name"
    assert all(r["content_url"] for r in rows), "item without PDF link"
    old = Path(out_path)
    if old.exists():  # keep dates already recorded, so a rebuild never erases retrieval history
        dates = {r["doc_id"]: r["retrieval_date"] for r in csv.DictReader(open(old, encoding="utf-8-sig"))}
        for r in rows:
            r["retrieval_date"] = dates.get(r["doc_id"], "")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
