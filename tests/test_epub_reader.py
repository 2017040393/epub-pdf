from epub_pdf.epub_reader import _extract_chapter


def test_extract_chapter_ignores_navigation_and_preserves_visible_blocks() -> None:
    chapter = _extract_chapter(
        b"<html><body><nav><p>Skip me</p></nav><h1>Part One</h1>"
        b"<p>First <em>paragraph</em>.</p><ul><li>Item</li></ul>"
        b"<blockquote>A quote</blockquote></body></html>",
        "Fallback",
    )
    assert chapter.title == "Part One"
    assert [(block.kind, block.text) for block in chapter.blocks] == [
        ("paragraph", "First paragraph."),
        ("list", "Item"),
        ("quote", "A quote"),
    ]
