from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from audiotran.domain.models import SubtitleCue


def make_cue(*, cue_id: int = 1, japanese_script: str = "こんにちは") -> SubtitleCue:
    return SubtitleCue(
        id=cue_id,
        start=0.0,
        end=1.0,
        japanese_script=japanese_script,
        japanese_recognized="",
        chinese="",
        confidence=None,
        source="script",
        reviewed=False,
    )


def test_translator_contract_preserves_order_and_forwards_glossary():
    from audiotran.translation import TranslationRequest, Translator

    class FakeTranslator(Translator):
        def __init__(self) -> None:
            self.received_request: TranslationRequest | None = None

        def translate(self, request: TranslationRequest) -> list[str]:
            self.received_request = request
            return [f"{text}-zh" for text in request.texts]

    request = TranslationRequest(
        texts=["一番目", "二番目"],
        glossary={"猫": "cat", "犬": "dog"},
    )
    translator = FakeTranslator()

    assert translator.translate(request) == ["一番目-zh", "二番目-zh"]
    assert translator.received_request is request
    assert translator.received_request.glossary == {"猫": "cat", "犬": "dog"}


def test_translation_error_leaves_original_cues_unchanged():
    from audiotran.translation import TranslationError, TranslationRequest, Translator

    class FailingTranslator(Translator):
        def translate(self, request: TranslationRequest) -> list[str]:
            raise TranslationError("translation failed")

    cue = make_cue(japanese_script="そのまま")
    original = cue.japanese_script, cue.japanese_recognized, cue.chinese
    translator = FailingTranslator()

    with pytest.raises(TranslationError, match="translation failed"):
        translator.translate(TranslationRequest(texts=[cue.japanese_script], glossary={}))

    assert (cue.japanese_script, cue.japanese_recognized, cue.chinese) == original


def test_local_translator_loads_model_lazily_and_uses_injected_loader(tmp_path: Path):
    from audiotran.translation import LocalTranslator, TranslationRequest

    calls: list[Path] = []

    def loader(model_path: Path):
        calls.append(model_path)

        def model(texts: list[str], glossary: dict[str, str]) -> list[str]:
            assert texts == ["こんにちは", "世界"]
            assert glossary == {"世界": "world"}
            return ["hello", "world"]

        return model

    translator = LocalTranslator(tmp_path / "model.bin", model_loader=loader)

    assert calls == []
    assert translator.translate(
        TranslationRequest(texts=["こんにちは", "世界"], glossary={"世界": "world"})
    ) == ["hello", "world"]
    assert calls == [tmp_path / "model.bin"]


def test_local_translator_raises_translation_error_for_mismatched_output_count(
    tmp_path: Path,
):
    from audiotran.translation import LocalTranslator, TranslationError, TranslationRequest

    translator = LocalTranslator(
        tmp_path / "model.bin",
        model_loader=lambda model_path: lambda texts, glossary: ["only one"],
    )

    with pytest.raises(TranslationError, match="returned 1 results for 2 texts"):
        translator.translate(TranslationRequest(texts=["a", "b"], glossary={}))


def test_local_translator_failure_leaves_request_texts_unchanged(tmp_path: Path):
    from audiotran.translation import LocalTranslator, TranslationError, TranslationRequest

    request = TranslationRequest(texts=["そのまま", "維持"], glossary={"維持": "keep"})
    original_texts = list(request.texts)
    original_glossary = dict(request.glossary)
    translator = LocalTranslator(
        tmp_path / "model.bin",
        model_loader=lambda model_path: lambda texts, glossary: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
    )

    with pytest.raises(TranslationError, match="local translation failed"):
        translator.translate(request)

    assert request.texts == original_texts
    assert request.glossary == original_glossary


def test_online_translator_sends_requested_payload_only_and_enforces_timeout():
    from audiotran.translation import OnlineTranslator, TranslationRequest

    captured: dict[str, object] = {}

    class Response:
        def read(self) -> bytes:
            return json.dumps({"translations": ["hello"]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def send(request, *, timeout: float):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        timeout=12.5,
        sender=send,
    )

    result = translator.translate(
        TranslationRequest(texts=["こんにちは"], glossary={"用語": "term"})
    )

    assert result == ["hello"]
    assert captured == {
        "url": "https://example.test/translate",
        "headers": {
            "Authorization": "Bearer secret-key",
            "Content-type": "application/json",
        },
        "body": {
            "texts": ["こんにちは"],
            "glossary": {"用語": "term"},
        },
        "timeout": 12.5,
    }


def test_online_translator_redacts_api_key_and_raises_stable_error():
    from audiotran.translation import OnlineTranslator, TranslationError, TranslationRequest

    def send(request, *, timeout: float):
        raise RuntimeError(f"boom with secret-key at {request.full_url}")

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        sender=send,
    )

    with pytest.raises(TranslationError) as exc_info:
        translator.translate(TranslationRequest(texts=["こんにちは"], glossary={}))

    assert str(exc_info.value) == "online translation failed"
    assert "secret-key" not in repr(exc_info.value)


def test_online_translator_redacts_http_error_without_reconstructing_it():
    from audiotran.translation import OnlineTranslator, TranslationError, TranslationRequest

    def send(request, *, timeout: float):
        raise HTTPError(
            request.full_url,
            503,
            "upstream secret-key failed",
            hdrs=None,
            fp=None,
        )

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        sender=send,
    )

    with pytest.raises(TranslationError) as exc_info:
        translator.translate(TranslationRequest(texts=["こんにちは"], glossary={}))

    assert str(exc_info.value) == "online translation failed"
    assert "secret-key" not in repr(exc_info.value)


def test_online_translator_rejects_malformed_top_level_json_shape():
    from audiotran.translation import OnlineTranslator, TranslationError, TranslationRequest

    class Response:
        status = 200

        def read(self) -> bytes:
            return json.dumps(["not", "a", "dict"]).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        sender=lambda request, timeout: Response(),
    )

    with pytest.raises(TranslationError, match="online translation failed"):
        translator.translate(TranslationRequest(texts=["こんにちは"], glossary={}))


def test_online_translator_rejects_injected_non_2xx_response():
    from audiotran.translation import OnlineTranslator, TranslationError, TranslationRequest

    class Response:
        status = 503

        def read(self) -> bytes:
            return json.dumps({"translations": ["hello"]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        sender=lambda request, timeout: Response(),
    )

    with pytest.raises(TranslationError, match="online translation failed"):
        translator.translate(TranslationRequest(texts=["こんにちは"], glossary={}))


def test_online_translator_failure_leaves_request_texts_unchanged():
    from audiotran.translation import OnlineTranslator, TranslationError, TranslationRequest

    request = TranslationRequest(texts=["そのまま", "維持"], glossary={"維持": "keep"})
    original_texts = list(request.texts)
    original_glossary = dict(request.glossary)

    def send(request, *, timeout: float):
        raise RuntimeError("secret-key transport failure")

    translator = OnlineTranslator(
        "https://example.test/translate",
        "secret-key",
        sender=send,
    )

    with pytest.raises(TranslationError, match="online translation failed"):
        translator.translate(request)

    assert request.texts == original_texts
    assert request.glossary == original_glossary
