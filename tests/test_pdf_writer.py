from pathlib import Path

from epub_pdf.models import Block, Book, Chapter
from epub_pdf.pdf_writer import write_pdf


def test_write_pdf_creates_a_valid_pdf(tmp_path: Path) -> None:
    output = tmp_path / "book.pdf"
    write_pdf(
        Book("Test Book", "A. Author", [Chapter("Chapter 1", [Block("Readable text.")])]),
        output,
        font_path=None,
    )
    assert output.read_bytes().startswith(b"%PDF-")
