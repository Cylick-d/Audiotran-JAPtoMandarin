from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Source = Literal["script", "asr"]


@dataclass(slots=True)
class SubtitleCue:
    id: int
    start: float
    end: float
    japanese_script: str
    japanese_recognized: str
    chinese: str
    confidence: float | None
    source: Source
    reviewed: bool

    def duration(self) -> float:
        return self.end - self.start

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.end < self.start:
            errors.append(f"cue {self.id} has an invalid time range")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            errors.append(f"cue {self.id} confidence must be between 0 and 1")
        return errors


@dataclass(slots=True)
class Project:
    audio_path: str
    image_path: str
    script_path: str | None
    cues: list[SubtitleCue] = field(default_factory=list)
    settings: dict[str, object] = field(default_factory=dict)

    def validate(self, check_filesystem: bool = False) -> list[str]:
        errors: list[str] = []

        for cue in self.cues:
            errors.extend(cue.validate())

        if check_filesystem:
            if not Path(self.audio_path).exists():
                errors.append(f"audio file does not exist: {self.audio_path}")
            if not Path(self.image_path).exists():
                errors.append(f"image file does not exist: {self.image_path}")

        return errors
