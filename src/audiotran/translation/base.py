from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class TranslationError(RuntimeError):
    """Stable translation adapter failure."""


@dataclass(slots=True)
class TranslationRequest:
    texts: list[str]
    glossary: dict[str, str] = field(default_factory=dict)


class Translator(ABC):
    @abstractmethod
    def translate(self, request: TranslationRequest) -> list[str]:
        raise NotImplementedError
