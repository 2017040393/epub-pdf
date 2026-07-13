from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Book, Chapter
from .translation import TranslationConfig, translate_book


class TranslationCheckpoint:
    """Durable, local-only translated chapter state for one output PDF."""

    version = 1

    def __init__(self, source: Path, output: Path, config: TranslationConfig) -> None:
        self.source = source
        self.path = output.with_suffix(".translation-progress.json")
        self._expected = {
            "version": self.version,
            "source_sha256": _file_sha256(source),
            "model": config.model,
            "target_language": config.target_language,
        }
        self._data = {**self._expected, "chapters": {}}

    def restore(self, book: Book) -> set[int]:
        if not self.path.is_file():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(data, dict) or any(data.get(key) != value for key, value in self._expected.items()):
            return set()
        chapters = data.get("chapters")
        if not isinstance(chapters, dict):
            return set()

        restored: set[int] = set()
        for raw_index, entry in chapters.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(book.chapters) or not isinstance(entry, dict):
                continue
            chapter = book.chapters[index]
            texts = entry.get("texts")
            indexes = [i for i, block in enumerate(chapter.blocks) if block.kind != "code"]
            if entry.get("block_count") != len(chapter.blocks) or not isinstance(texts, list):
                continue
            if len(texts) != len(indexes) or not all(isinstance(text, str) for text in texts):
                continue
            for block_index, text in zip(indexes, texts):
                chapter.blocks[block_index].text = text
            restored.add(index)
        self._data = data
        return restored

    def save_chapter(self, chapter_index: int, chapter: Chapter) -> None:
        chapters = self._data.setdefault("chapters", {})
        chapters[str(chapter_index)] = {
            "block_count": len(chapter.blocks),
            "texts": [block.text for block in chapter.blocks if block.kind != "code"],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


def translate_book_with_checkpoint(
    book: Book,
    source: Path,
    output: Path,
    config: TranslationConfig,
    progress=None,
) -> tuple[Book, TranslationCheckpoint]:
    checkpoint = TranslationCheckpoint(source, output, config)
    completed = checkpoint.restore(book)
    if completed and progress:
        progress(f"Resuming from checkpoint: {len(completed)} completed chapter(s).")
    translated = translate_book(
        book,
        config,
        progress=progress,
        completed_chapter_indexes=completed,
        on_chapter_complete=checkpoint.save_chapter,
    )
    return translated, checkpoint


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
