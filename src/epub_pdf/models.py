from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """A visible content block extracted from an EPUB document."""

    text: str
    kind: str = "paragraph"
    level: int = 0


@dataclass
class Chapter:
    title: str
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Book:
    title: str
    author: str | None
    chapters: list[Chapter]
