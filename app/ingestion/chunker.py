"""Split cleaned pages into chunks: one per Article, long articles cut further with overlap (DATA-03, DATA-04)."""
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.schemas.document import Chunk, ParsedPage

# A real heading sits alone on its line; "Article (7) of the above..." mid-sentence is not a heading.
ARTICLE_HEADING = re.compile(r"^Article\s*\((\d+)\)[ \t]*$", re.MULTILINE)


def join_pages(pages: list[ParsedPage]) -> tuple[str, list[int]]:
    """Join pages into one text and record each character's page number, so chunks can report their pages."""
    text, page_of = "", []
    for page in pages:
        piece = page.text + "\n"
        text += piece
        page_of += [page.page_number] * len(piece)
    return text, page_of


def split_articles(pages: list[ParsedPage], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Return one Chunk per Article (plus opening text); an article longer than chunk_size is cut with overlap."""
    text, page_of = join_pages(pages)
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True)
    heads = list(ARTICLE_HEADING.finditer(text))
    starts = [0] + [m.start() for m in heads if m.start() > 0]
    labels = [None] * (1 if not heads or heads[0].start() > 0 else 0) + [f"Article ({m.group(1)})" for m in heads]
    chunks = []
    for start, end, label in zip(starts, starts[1:] + [len(text)], labels):
        body = text[start:end]
        if not body.strip():
            continue
        offset = start + len(body) - len(body.lstrip())  # where the article's first real character sits in `text`
        for piece in splitter.create_documents([body.strip()]):
            index = piece.metadata["start_index"]
            if index < 0:  # the splitter could not locate its own piece: refuse to guess a page number
                raise ValueError(f"cannot locate chunk of {label} in the document text")
            first = offset + index
            chunks.append(Chunk(article=label, text=piece.page_content,
                                page_start=page_of[first], page_end=page_of[first + len(piece.page_content) - 1]))
    return chunks
