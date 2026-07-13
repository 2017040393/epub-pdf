from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .epub_reader import read_epub
from .models import Book, Chapter
from .pdf_writer import write_pdf
from .translation import OpenAICompatibleTranslator, TranslationConfig, TranslationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert an EPUB book to a readable PDF.")
    parser.add_argument("input", type=Path, help="source EPUB path")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output PDF path")
    parser.add_argument("--title", help="override the PDF title")
    parser.add_argument("--author", help="override the PDF author")
    parser.add_argument("--font", type=Path, help="override the auto-detected TrueType font path")
    parser.add_argument("--font-size", type=float, default=10.5, help="body font size (default: 10.5)")
    parser.add_argument("--translate", action="store_true", help="translate body paragraphs through an LLM")
    parser.add_argument("--target-language", default="简体中文", help="translation target (default: 简体中文)")
    parser.add_argument("--model", default="gpt-5.6-terra", help="model name")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="OpenAI-compatible API root")
    parser.add_argument("--api-key", help="API key; defaults to OPENAI_API_KEY")
    parser.add_argument("--chunk-size", type=int, default=20000, help="max source chars per translation request")
    return parser


def translate_book(book: Book, config: TranslationConfig, progress=None) -> Book:
    translator = OpenAICompatibleTranslator(config)
    translated_chapters: list[Chapter] = []
    for number, chapter in enumerate(book.chapters, start=1):
        translatable_indexes = [i for i, block in enumerate(chapter.blocks) if block.kind != "code"]
        source = [chapter.blocks[i].text for i in translatable_indexes]
        if source:
            message = f"Translating chapter {number}/{len(book.chapters)}: {chapter.title}"
            if progress:
                progress(message)
            else:
                print(message, file=sys.stderr)
            translated = translator.translate_paragraphs(source)
            for index, text in zip(translatable_indexes, translated):
                chapter.blocks[index].text = text
        translated_chapters.append(chapter)
    return Book(book.title, book.author, translated_chapters)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.is_file():
        print(f"Input EPUB not found: {args.input}", file=sys.stderr)
        return 2
    try:
        book = read_epub(args.input)
        if args.title:
            book.title = args.title
        if args.author:
            book.author = args.author
        if args.translate:
            book = translate_book(book, TranslationConfig(
                model=args.model, target_language=args.target_language,
                api_base=args.api_base, api_key=args.api_key, chunk_size=args.chunk_size,
            ))
        font = resolve_font(args.font)
        if font:
            print(f"Using font: {font}", file=sys.stderr)
        print(f"Writing PDF: {args.output}", file=sys.stderr)
        write_pdf(book, args.output, font, args.font_size)
    except (ValueError, OSError, TranslationError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    print(f"Done: {args.output}")
    return 0


def resolve_font(explicit_font: Path | None) -> Path | None:
    if explicit_font:
        return explicit_font
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for filename in ("simhei.ttf", "NotoSansSC-Regular.ttf", "Deng.ttf"):
        candidate = windows_dir / "Fonts" / filename
        if candidate.is_file():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
