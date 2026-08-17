from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from audiotran.domain.models import SubtitleCue


class SpeechRecognitionError(ValueError):
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"unable to load speech recognition model: {model_name}")


TranscriberFactory = Callable[[str, str], Any]


class SpeechRecognizer:
    def __init__(
        self,
        model_name: str,
        device: str = "auto",
        transcriber_factory: TranscriberFactory | None = None,
    ):
        self.model_name = model_name
        self.device = device
        factory = _load_transcriber if transcriber_factory is None else transcriber_factory

        try:
            self._transcriber = factory(model_name, device)
        except Exception as exc:
            raise SpeechRecognitionError(model_name) from exc

    def transcribe(self, path: Path) -> list[SubtitleCue]:
        path = Path(path)
        segments, _info = self._transcriber.transcribe(path)

        cues: list[SubtitleCue] = []
        for index, segment in enumerate(segments, start=1):
            cues.append(
                SubtitleCue(
                    id=index,
                    start=float(segment.start),
                    end=float(segment.end),
                    japanese_script="",
                    japanese_recognized=str(segment.text).strip(),
                    chinese="",
                    confidence=None,
                    source="asr",
                    reviewed=False,
                )
            )
        return cues


def _load_transcriber(model_name: str, device: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device=device)
