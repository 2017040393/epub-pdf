from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from .models import Block, Book, Chapter


def read_epub(path: Path) -> Book:
    """Read visible content in the EPUB spine order."""
    source = epub.read_epub(str(path))
    title = _metadata_value(source, "title") or path.stem
    author = _metadata_value(source, "creator")

    items_by_id = {item.get_id(): item for item in source.get_items_of_type(ITEM_DOCUMENT)}
    spine_ids = [entry[0] if isinstance(entry, tuple) else entry for entry in source.spine]
    ordered_items = [items_by_id[item_id] for item_id in spine_ids if item_id in items_by_id]
    if not ordered_items:
        ordered_items = list(items_by_id.values())

    chapters = []
    for index, item in enumerate(ordered_items, start=1):
        chapter = _extract_chapter(item.get_content(), fallback_title=f"Chapter {index}")
        if chapter.blocks:
            chapters.append(chapter)
    if not chapters:
        raise ValueError("No readable XHTML documents were found in this EPUB.")
    return Book(title=title, author=author, chapters=chapters)


def _metadata_value(book: epub.EpubBook, name: str) -> str | None:
    values = book.get_metadata("DC", name)
    return values[0][0].strip() if values and values[0][0].strip() else None


def _extract_chapter(content: bytes, fallback_title: str) -> Chapter:
    soup = BeautifulSoup(content, "html.parser")
    for element in soup(["script", "style", "svg", "nav", "noscript", "img"]):
        element.decompose()
    body = soup.body or soup
    heading = body.find(["h1", "h2", "h3"])
    title = _clean_text(heading.get_text(" ", strip=True)) if heading else fallback_title
    blocks: list[Block] = []
    for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"]):
        # Nested tags are represented by their parent visible block only.
        if element.find_parent(["p", "li", "blockquote", "pre"]):
            continue
        text = _clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if element.name.startswith("h"):
            if text == title:
                continue
            blocks.append(Block(text, "heading", int(element.name[1])))
        elif element.name == "li":
            blocks.append(Block(text, "list"))
        elif element.name == "blockquote":
            blocks.append(Block(text, "quote"))
        elif element.name == "pre":
            blocks.append(Block(text, "code"))
        else:
            blocks.append(Block(text))
    return Chapter(title or fallback_title, blocks)


def _clean_text(value: str) -> str:
    value = " ".join(value.split())
    return re.sub(r"\s+([,.;:!?])", r"\1", value)
