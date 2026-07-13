from epub_pdf.cli import build_parser


def test_cli_uses_long_context_translation_defaults() -> None:
    args = build_parser().parse_args(["book.epub", "-o", "book.pdf"])
    assert args.model == "gpt-5.6-terra"
    assert args.chunk_size == 20000
