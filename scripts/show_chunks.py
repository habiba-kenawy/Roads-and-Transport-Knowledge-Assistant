"""Print stored chunks so a human can inspect them: `python -m scripts.show_chunks <doc_id> [max_chunks]`."""
import sqlite3
import sys

from app.config import Settings


def main(doc_id: str, limit: int = 5) -> None:
    """Show metadata and the start of each chunk of one document."""
    conn = sqlite3.connect(Settings().db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_index LIMIT ?", (doc_id, limit)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()[0]
    print(f"{doc_id}: {total} chunks (showing {len(rows)})")
    for r in rows:
        print(f"\n--- {r['chunk_id']} | {r['article']} | pages {r['page_start']}-{r['page_end']} | {len(r['text'])} chars")
        print(f"    {r['title']} | {r['doc_type']} {r['number']}/{r['year']} | {r['authority']} | {r['status']}")
        print("    " + r["text"][:300].replace("\n", "\n    "))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
