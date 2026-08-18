from __future__ import annotations

from pathlib import Path
from typing import Callable

from .base import TranslationError, TranslationRequest, Translator

TranslationModel = Callable[[list[str], dict[str, str]], list[str]]
TranslationModelLoader = Callable[[Path], TranslationModel]


class LocalTranslator(Translator):
    def __init__(
        self,
        model_path: Path,
        model_loader: TranslationModelLoader | None = None,
    ) -> None:
        self._model_path = model_path
        self._model_loader = model_loader or _missing_model_loader
        self._model: TranslationModel | None = None

    def translate(
        self,
        request: TranslationRequest,
        progress_callback: Callable[[int], None] | None = None,
    ) -> list[str]:
        model = self._get_model()

        try:
            translations: list[str] = []
            batch_size = 8
            batches = max(1, (len(request.texts) + batch_size - 1) // batch_size)
            for batch_index in range(batches):
                start = batch_index * batch_size
                batch = list(request.texts[start : start + batch_size])
                translations.extend(model(batch, dict(request.glossary)))
                if progress_callback is not None:
                    progress_callback(round((batch_index + 1) / batches * 100))
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError("local translation failed") from exc

        return _validate_translation_count(translations, len(request.texts))

    def _get_model(self) -> TranslationModel:
        if self._model is None:
            self._model = self._model_loader(self._model_path)
        return self._model


def _missing_model_loader(model_path: Path) -> TranslationModel:
    raise TranslationError(f"no local translation model loader configured for {model_path}")


def _validate_translation_count(translations: list[str], expected_count: int) -> list[str]:
    if len(translations) != expected_count:
        raise TranslationError(
            f"translator returned {len(translations)} results for {expected_count} texts"
        )
    return translations
