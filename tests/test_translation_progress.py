from pathlib import Path

from epub_pdf.models import Block, Book, Chapter
from epub_pdf.translation import TranslationConfig
from epub_pdf.translation_progress import TranslationCheckpoint


def _book(text: str) -> Book:
    return Book("Book", None, [Chapter("One", [Block(text), Block("Code", "code")])])


def test_checkpoint_restores_completed_chapter(tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    output = tmp_path / "book.pdf"
    source.write_bytes(b"source")
    checkpoint = TranslationCheckpoint(source, output, TranslationConfig(api_key="test"))
    translated = _book("Translated text")
    checkpoint.save_chapter(0, translated.chapters[0])

    restored_book = _book("Source text")
    assert checkpoint.restore(restored_book) == {0}
    assert restored_book.chapters[0].blocks[0].text == "Translated text"
    assert restored_book.chapters[0].blocks[1].text == "Code"


def test_checkpoint_is_not_reused_for_a_different_model(tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    output = tmp_path / "book.pdf"
    source.write_bytes(b"source")
    checkpoint = TranslationCheckpoint(source, output, TranslationConfig(api_key="test"))
    checkpoint.save_chapter(0, _book("Translated text").chapters[0])

    other_model = TranslationCheckpoint(source, output, TranslationConfig(model="other", api_key="test"))
    restored_book = _book("Source text")
    assert other_model.restore(restored_book) == set()
    assert restored_book.chapters[0].blocks[0].text == "Source text"
