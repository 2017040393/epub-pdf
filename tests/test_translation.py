from epub_pdf.translation import _unwrap_json_fence, chunk_paragraphs


def test_chunk_paragraphs_preserves_order_and_limit() -> None:
    paragraphs = ["one" * 50, "two" * 50, "three" * 50]
    chunks = chunk_paragraphs(paragraphs, 310)
    assert chunks == [[paragraphs[0], paragraphs[1]], [paragraphs[2]]]


def test_chunk_paragraphs_keeps_an_oversized_paragraph_intact() -> None:
    assert chunk_paragraphs(["a" * 250], 100) == [["a" * 250]]


def test_unwrap_json_markdown_fence() -> None:
    assert _unwrap_json_fence("```json\n[\"ok\"]\n```") == "[\"ok\"]"
