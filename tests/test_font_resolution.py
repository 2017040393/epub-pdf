from pathlib import Path

from epub_pdf.cli import _resolve_font


def test_explicit_font_takes_priority(tmp_path: Path) -> None:
    font = tmp_path / "custom.ttf"
    font.touch()
    assert _resolve_font(font) == font
