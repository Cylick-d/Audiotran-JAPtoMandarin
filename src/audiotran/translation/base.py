from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections.abc import Callable


class TranslationError(RuntimeError):
    """Stable translation adapter failure."""


@dataclass(slots=True)
class TranslationRequest:
    texts: list[str]
    glossary: dict[str, str] = field(default_factory=dict)


class Translator(ABC):
    @abstractmethod
    def translate(
        self,
        request: TranslationRequest,
        progress_callback: Callable[[int], None] | None = None,
    ) -> list[str]:
        raise NotImplementedError
