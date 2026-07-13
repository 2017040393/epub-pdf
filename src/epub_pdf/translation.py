from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TranslationError(RuntimeError):
    """Raised when a translation request cannot produce usable text."""


@dataclass(frozen=True)
class TranslationConfig:
    model: str = "gpt-5.6-terra"
    target_language: str = "简体中文"
    api_base: str = "https://api.openai.com/v1"
    api_key: str | None = None
    chunk_size: int = 20000
    timeout_seconds: int = 90

    def resolved_api_key(self) -> str:
        key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise TranslationError(
                "Translation requires --api-key or the OPENAI_API_KEY environment variable."
            )
        return key


def chunk_paragraphs(paragraphs: list[str], max_chars: int) -> list[list[str]]:
    """Group paragraphs while preserving a one-to-one source/output mapping."""
    if max_chars < 100:
        raise ValueError("chunk_size must be at least 100 characters")

    chunks: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        size = len(paragraph) + (2 if current else 0)
        if current and current_size + size > max_chars:
            chunks.append(current)
            current, current_size = [], 0
        # A very long paragraph is kept intact so its translation can be mapped
        # back to exactly one EPUB block.
        current.append(paragraph)
        current_size += len(paragraph) + (2 if len(current) > 1 else 0)
    if current:
        chunks.append(current)
    return chunks


class OpenAICompatibleTranslator:
    def __init__(self, config: TranslationConfig) -> None:
        self.config = config
        self.api_key = config.resolved_api_key()

    def translate_paragraphs(self, paragraphs: list[str]) -> list[str]:
        translated: list[str] = []
        for chunk in chunk_paragraphs(paragraphs, self.config.chunk_size):
            result = self._translate_chunk(chunk)
            if len(result) != len(chunk):
                raise TranslationError(
                    f"Model returned {len(result)} paragraphs for {len(chunk)} source paragraphs."
                )
            translated.extend(result)
        return translated

    def _translate_chunk(self, paragraphs: list[str]) -> list[str]:
        prompt = (
            f"Translate every item in this JSON array into {self.config.target_language}. "
            "Keep the same item count and order. Preserve names, numbers, code, and inline markup. "
            "Return only a valid JSON array of translated strings.\n\n"
            + json.dumps(paragraphs, ensure_ascii=False)
        )
        payload = json.dumps(
            {
                "model": self.config.model,
                "instructions": "You are a precise literary translator. Follow the output format exactly.",
                "input": prompt,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        url = self.config.api_base.rstrip("/") + "/responses"
        request = Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=self.config.timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
                content = _response_text(body)
                parsed = json.loads(_unwrap_json_fence(content))
                if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                    raise TranslationError("Model response was not a JSON array of strings.")
                return parsed
            except (HTTPError, URLError, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
                if attempt == 2:
                    raise TranslationError(f"Translation request failed: {exc}") from exc
                time.sleep(2**attempt)
        raise AssertionError("unreachable")


def _unwrap_json_fence(value: str) -> str:
    if value.startswith("```") and value.endswith("```"):
        return value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return value


def _response_text(response: dict) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    if parts:
        return "".join(parts).strip()
    raise ValueError("Responses API response did not include output_text.")
