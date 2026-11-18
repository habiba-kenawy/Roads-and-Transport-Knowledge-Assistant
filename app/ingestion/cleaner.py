"""Clean parsed pages: drop repeated footers, page-number lines and decoration; keep real content (DATA-03)."""
import math
import re
from collections import Counter

from app.schemas.document import ParsedPage

EDGE_LINES = 6        # footers/headers live in the first or last few lines of a page
MIN_PAGE_SHARE = 0.5  # a line must repeat on at least half the pages (and on 2+ pages)
MIN_REPEATED_CHARS = 8  # short repeats ("AED" in a fee table) are content, not footers; found on dlp-1341
PAGE_NUMBER = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.IGNORECASE)
TATWEEL = "ـ"    # Arabic stretching character, used here only as a decorative rule


def normalize(line: str) -> str:
    """Collapse whitespace so the same footer matches on every page."""
    return " ".join(line.split())


def is_decoration(line: str) -> bool:
    """True for a non-empty line with no real letters or digits (rules made of tatweel, dashes, etc.)."""
    return bool(line.strip()) and not any(ch.isalnum() and ch != TATWEEL for ch in line)


def edge_zone(lines: list[str]) -> set[int]:
    """Indexes of the first and last EDGE_LINES lines, where repeated furniture lives."""
    return set(range(min(EDGE_LINES, len(lines)))) | set(range(max(0, len(lines) - EDGE_LINES), len(lines)))


def repeated_edge_lines(pages: list[ParsedPage]) -> set[str]:
    """Return normalized alines found at the page edges on at least half the pages (and at least 2)."""
    counts: Counter[str] = Counter()
    for page in pages:
        lines = page.text.splitlines()
        counts.update({normalize(lines[i]) for i in edge_zone(lines) if normalize(lines[i])})  # set: once per page
    needed = max(2, math.ceil(len(pages) * MIN_PAGE_SHARE))
    return {line for line, count in counts.items() if count >= needed and len(line) >= MIN_REPEATED_CHARS}


def clean_pages(pages: list[ParsedPage]) -> list[ParsedPage]:
    """Return pages without furniture; page numbers are kept so locators still match the PDF."""
    repeated = repeated_edge_lines(pages)
    cleaned = []
    for page in pages:
        lines = page.text.splitlines()
        edges = edge_zone(lines)
        keep = [
            line.rstrip() for i, line in enumerate(lines)
            if normalize(line)
            and not PAGE_NUMBER.match(normalize(line))
            and not is_decoration(line)
            and not (i in edges and normalize(line) in repeated)  # a repeat in mid-page is real content
        ]
        cleaned.append(ParsedPage(page_number=page.page_number, text="\n".join(keep)))
    return cleaned
