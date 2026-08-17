from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(slots=True)
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float


class FakeTranscriber:
    def __init__(self, segments: list[FakeSegment]):
        self.segments = segments
        self.calls: list[Path] = []

    def transcribe(self, path: Path):
        self.calls.append(Path(path))
        return list(self.segments), {"language": "ja"}


def test_speech_recognizer_maps_segments_into_subtitle_cues(tmp_path: Path):
    from audiotran.domain.models import SubtitleCue
    from audiotran.media import SpeechRecognizer

    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"placeholder")
    transcriber = FakeTranscriber(
        [
            FakeSegment(start=0.5, end=1.75, text=" こんにちは ", avg_logprob=-0.2),
            FakeSegment(start=2.0, end=3.0, text="さようなら", avg_logprob=-0.7),
        ]
    )

    recognizer = SpeechRecognizer(
        model_name="tiny",
        transcriber_factory=lambda model_name, device: transcriber,
    )

    assert recognizer.transcribe(audio_path) == [
        SubtitleCue(
            id=1,
            start=0.5,
            end=1.75,
            japanese_script="",
            japanese_recognized="こんにちは",
            chinese="",
            confidence=None,
            source="asr",
            reviewed=False,
        ),
        SubtitleCue(
            id=2,
            start=2.0,
            end=3.0,
            japanese_script="",
            japanese_recognized="さようなら",
            chinese="",
            confidence=None,
            source="asr",
            reviewed=False,
        ),
    ]
    assert transcriber.calls == [audio_path]


def test_speech_recognizer_raises_clean_error_when_model_cannot_load():
    from audiotran.media import SpeechRecognitionError, SpeechRecognizer

    def missing_model(_model_name: str, _device: str):
        raise FileNotFoundError("missing model")

    with pytest.raises(SpeechRecognitionError, match="tiny"):
        SpeechRecognizer(model_name="tiny", transcriber_factory=missing_model)
