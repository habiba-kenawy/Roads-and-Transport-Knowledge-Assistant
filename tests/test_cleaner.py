"""Tests for clean_pages. All text below is FAKE; it only mimics the layout problems seen in the real PDFs."""
from app.ingestion.cleaner import clean_pages
from app.schemas.document import ParsedPage

FOOTER = ["FAKE Law No. (1) of 2000 Concerning Fake Roads in the", "Fake Emirate", "Page {n} of 3"]
RULE = "ـ" * 30  # tatweel decoration line


def fake_page(n: int, body: list[str], footer: bool = True) -> ParsedPage:
    """Build a FAKE page: footer lines first (as pypdf emits them), then the body."""
    lines = [f.format(n=n) for f in FOOTER] if footer else []
    return ParsedPage(page_number=n, text="\n".join(lines + body) + "  ")


def test_repeated_footer_page_numbers_and_decoration_are_removed_but_articles_kept() -> None:
    """DATA-03: furniture goes, article boundaries and page numbers (locators) stay."""
    pages = [fake_page(1, [RULE, "Article (1)", "FAKE rule one."]), fake_page(2, ["Article (2)", "FAKE rule two."]),
             fake_page(3, ["Article (3)", "FAKE rule three."])]
    cleaned = clean_pages(pages)
    assert [p.page_number for p in cleaned] == [1, 2, 3]
    assert cleaned[0].text == "Article (1)\nFAKE rule one."
    assert cleaned[1].text == "Article (2)\nFAKE rule two."


def test_short_repeated_token_is_kept_because_it_is_content() -> None:
    """Regression for dlp-1341: 'AED' in a fee table repeats on every page but is real content."""
    pages = [fake_page(n, ["Fee", "AED", "1,000.00", "AED"], footer=False) for n in (1, 2, 3)]
    assert all(p.text.splitlines().count("AED") == 2 for p in clean_pages(pages))


def test_repeated_line_in_the_middle_of_a_page_is_kept() -> None:
    """Protects real headings that repeat: only page-edge repeats count as furniture."""
    middle = ["FAKE heading that repeats"] + [f"FAKE body line {i}" for i in range(10)] + ["FAKE heading that repeats"] + [f"FAKE tail {i}" for i in range(10)]
    cleaned = clean_pages([ParsedPage(page_number=n, text="\n".join(middle)) for n in (1, 2)])
    assert cleaned[0].text.count("FAKE heading that repeats") == 1  # the one in the middle survives


def test_footnote_that_appears_once_is_kept() -> None:
    """Protects real content such as the translation disclaimer, which appears on one page only."""
    note = "FAKE disclaimer: the Arabic text prevails in case of conflict."
    cleaned = clean_pages([fake_page(1, ["Article (1)", note]), fake_page(2, ["Article (2)"]), fake_page(3, ["Article (3)"])])
    assert note in cleaned[0].text


def test_single_page_document_keeps_its_footer_but_drops_page_number_line() -> None:
    """Documents the known limit: with one page nothing 'repeats', so the footer stays (harmless duplicate)."""
    cleaned = clean_pages([fake_page(1, ["Article (1)"])])
    assert "FAKE Law No. (1) of 2000" in cleaned[0].text
    assert "Page 1 of 3" not in cleaned[0].text
