from __future__ import annotations

from .base import TranslationError, TranslationRequest, Translator
from .local import LocalTranslator
from .online import OnlineTranslator

__all__ = [
    "LocalTranslator",
    "OnlineTranslator",
    "TranslationError",
    "TranslationRequest",
    "Translator",
]
