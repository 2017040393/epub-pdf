from pathlib import Path

from ebooklib import epub

from epub_pdf.cli import main


def test_cli_converts_a_minimal_epub(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    output = tmp_path / "result.pdf"
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("Test EPUB")
    book.add_author("Test Author")
    chapter = epub.EpubHtml(title="First Chapter", file_name="chapter.xhtml", lang="en")
    chapter.content = "<html><body><h1>First Chapter</h1><p>Hello reader.</p></body></html>"
    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    epub.write_epub(str(source), book)

    assert main([str(source), "-o", str(output)]) == 0
    assert output.read_bytes().startswith(b"%PDF-")
