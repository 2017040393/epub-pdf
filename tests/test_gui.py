from pathlib import Path

from epub_pdf.gui import TARGET_LANGUAGES, default_output_path, normalize_output_path


def test_default_output_path_replaces_epub_extension() -> None:
    assert default_output_path(Path("C:/books/example.epub")) == Path("C:/books/example.pdf")


def test_normalize_output_path_adds_pdf_suffix() -> None:
    assert normalize_output_path(Path("C:/books/result")) == Path("C:/books/result.pdf")


def test_target_language_list_includes_default_chinese() -> None:
    assert TARGET_LANGUAGES[0] == "简体中文"
    assert "English" in TARGET_LANGUAGES
