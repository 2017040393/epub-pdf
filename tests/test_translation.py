import json
from http.client import RemoteDisconnected

from epub_pdf.translation import (
    OpenAICompatibleTranslator,
    TranslationConfig,
    _response_text,
    _unwrap_json_fence,
    chunk_paragraphs,
    fetch_available_models,
)


def test_translation_defaults_are_optimized_for_long_context() -> None:
    config = TranslationConfig()
    assert config.model == "gpt-5.6-terra"
    assert config.chunk_size == 20000


def test_chunk_paragraphs_preserves_order_and_limit() -> None:
    paragraphs = ["one" * 50, "two" * 50, "three" * 50]
    chunks = chunk_paragraphs(paragraphs, 310)
    assert chunks == [[paragraphs[0], paragraphs[1]], [paragraphs[2]]]


def test_chunk_paragraphs_keeps_an_oversized_paragraph_intact() -> None:
    assert chunk_paragraphs(["a" * 250], 100) == [["a" * 250]]


def test_unwrap_json_markdown_fence() -> None:
    assert _unwrap_json_fence("```json\n[\"ok\"]\n```") == "[\"ok\"]"


def test_response_text_falls_back_to_standard_output_items() -> None:
    assert _response_text({
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "[\"译文\"]"}]}],
    }) == "[\"译文\"]"


def test_translator_calls_responses_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b'{"output_text": "[\\\"Translated\\\"]"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("epub_pdf.translation.urlopen", fake_urlopen)
    translator = OpenAICompatibleTranslator(TranslationConfig(api_base="https://example.test/v1", api_key="test-key"))

    assert translator.translate_paragraphs(["Source text"]) == ["Translated"]
    assert captured["url"] == "https://example.test/v1/responses"
    assert captured["payload"] == {
        "model": "gpt-5.6-terra",
        "instructions": "You are a precise literary translator. Follow the output format exactly.",
        "input": (
            "Translate every item in this JSON array into 简体中文. Keep the same item count and order. "
            "Preserve names, numbers, code, and inline markup. Return only a valid JSON array of translated strings.\n\n"
            '["Source text"]'
        ),
    }


def test_fetch_available_models_uses_models_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b'{"data": [{"id": "model-b"}, {"id": "model-a"}, {"id": "model-a"}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        return FakeResponse()

    monkeypatch.setattr("epub_pdf.translation.urlopen", fake_urlopen)

    assert fetch_available_models(TranslationConfig(api_base="https://example.test/v1", api_key="test-key")) == ["model-a", "model-b"]
    assert captured == {"url": "https://example.test/v1/models", "method": "GET"}


def test_translator_retries_remote_disconnect(monkeypatch) -> None:
    attempts = 0

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b'{"output_text": "[\\\"Translated\\\"]"}'

    def fake_urlopen(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RemoteDisconnected("Remote end closed connection without response")
        return FakeResponse()

    monkeypatch.setattr("epub_pdf.translation.urlopen", fake_urlopen)
    retries: list[str] = []
    translator = OpenAICompatibleTranslator(TranslationConfig(api_key="test-key"), on_retry=retries.append)
    translator.retry_base_seconds = 0

    assert translator.translate_paragraphs(["Source text"]) == ["Translated"]
    assert attempts == 3
    assert retries == [
        "Temporary API connection issue. Retrying current translation block in 0 second(s) (2/5).",
        "Temporary API connection issue. Retrying current translation block in 0 second(s) (3/5).",
    ]
