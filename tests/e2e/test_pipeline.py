from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audiotran.domain import Project, SubtitleCue
from audiotran.export import ExportResult, SubtitleStyle
from audiotran.io import load_project
from audiotran.media import MediaInfo
from audiotran.translation import TranslationRequest


def make_cue(
    cue_id: int,
    start: float,
    end: float,
    recognized: str,
) -> SubtitleCue:
    return SubtitleCue(
        id=cue_id,
        start=start,
        end=end,
        japanese_script="",
        japanese_recognized=recognized,
        chinese="",
        confidence=0.95,
        source="asr",
        reviewed=False,
    )


@dataclass
class FakeRecognizer:
    cues: list[SubtitleCue]
    calls: list[Path]

    def transcribe(self, path: Path) -> list[SubtitleCue]:
        self.calls.append(Path(path))
        return [
            SubtitleCue(
                id=cue.id,
                start=cue.start,
                end=cue.end,
                japanese_script=cue.japanese_script,
                japanese_recognized=cue.japanese_recognized,
                chinese=cue.chinese,
                confidence=cue.confidence,
                source=cue.source,
                reviewed=cue.reviewed,
            )
            for cue in self.cues
        ]


@dataclass
class FakeTranslator:
    outputs: list[str]
    requests: list[TranslationRequest]

    def translate(self, request: TranslationRequest) -> list[str]:
        self.requests.append(request)
        return list(self.outputs)


@dataclass
class FakeExporter:
    calls: list[tuple[Path, Path, Path, Path]]

    def __call__(
        self,
        audio: Path,
        image: Path,
        subtitle_file: Path,
        output: Path,
    ) -> ExportResult:
        self.calls.append((Path(audio), Path(image), Path(subtitle_file), Path(output)))
        output.write_text("video placeholder", encoding="utf-8")
        return ExportResult(
            video_path=output,
            subtitle_paths=[subtitle_file],
            log_path=output.with_suffix(".log"),
        )


@dataclass
class FakeProbe:
    calls: list[Path]

    def __call__(self, path: Path) -> MediaInfo:
        self.calls.append(Path(path))
        return MediaInfo(duration=3.0, sample_rate=48_000, channels=2, format_name="wav")


def test_pipeline_runs_script_alignment_translation_and_export(tmp_path: Path):
    from audiotran.pipeline import PipelineFacade

    audio_path = tmp_path / "audio.wav"
    image_path = tmp_path / "cover.png"
    script_path = tmp_path / "script.txt"
    output_path = tmp_path / "rendered.mp4"

    audio_path.write_text("audio", encoding="utf-8")
    image_path.write_text("image", encoding="utf-8")
    script_path.write_text("今日は。\nいい天気です。", encoding="utf-8")

    recognizer = FakeRecognizer(
        cues=[
            make_cue(1, 0.0, 1.5, "今日は"),
            make_cue(2, 1.5, 3.0, "いい天気です"),
        ],
        calls=[],
    )
    translator = FakeTranslator(outputs=["Today.", "Nice weather."], requests=[])
    exporter = FakeExporter(calls=[])
    probe = FakeProbe(calls=[])
    pipeline = PipelineFacade(
        recognizer=recognizer,
        translator=translator,
        exporter=exporter,
        media_probe=probe,
    )
    project = Project(
        audio_path=str(audio_path),
        image_path=str(image_path),
        script_path=str(script_path),
        cues=[],
        settings={"display_mode": "bilingual"},
    )

    artifacts = pipeline.run(
        project=project,
        output_path=output_path,
        mode="bilingual",
        glossary={"天気": "weather"},
        style=SubtitleStyle(
            font_name="Arial",
            font_size=28,
            primary_color="&H00FFFFFF",
            outline_color="&H00000000",
            back_color="&H00000000",
        ),
    )

    assert probe.calls == [audio_path]
    assert recognizer.calls == [audio_path]
    assert [request.texts for request in translator.requests] == [["今日は。", "いい天気です。"]]
    assert translator.requests[0].glossary == {"天気": "weather"}
    assert exporter.calls == [(audio_path, image_path, artifacts.ass_path, output_path)]
    assert artifacts.project_path.exists()
    assert artifacts.srt_path.exists()
    assert artifacts.ass_path.exists()
    assert artifacts.export_result.video_path.exists()
    assert artifacts.export_result.video_path.read_text(encoding="utf-8") == "video placeholder"

    reopened = load_project(artifacts.project_path)

    assert [cue.japanese_script for cue in reopened.cues] == ["今日は。", "いい天気です。"]
    assert [cue.japanese_recognized for cue in reopened.cues] == ["今日は", "いい天気です"]
    assert [cue.chinese for cue in reopened.cues] == ["Today.", "Nice weather."]
    assert [cue.source for cue in reopened.cues] == ["script", "script"]
    assert "今日は。" in artifacts.srt_path.read_text(encoding="utf-8")
    assert "Nice weather." in artifacts.srt_path.read_text(encoding="utf-8")
    assert "今日は。\\NNice weather." not in artifacts.ass_path.read_text(encoding="utf-8")
    assert "今日は。\\NToday." in artifacts.ass_path.read_text(encoding="utf-8")


def test_pipeline_falls_back_to_asr_when_project_has_no_script(tmp_path: Path):
    from audiotran.pipeline import PipelineFacade

    audio_path = tmp_path / "audio.wav"
    image_path = tmp_path / "cover.png"
    output_path = tmp_path / "rendered.mp4"

    audio_path.write_text("audio", encoding="utf-8")
    image_path.write_text("image", encoding="utf-8")

    recognizer = FakeRecognizer(
        cues=[
            make_cue(1, 0.0, 1.0, "そのまま"),
            make_cue(2, 1.0, 2.0, "続き"),
        ],
        calls=[],
    )
    translator = FakeTranslator(outputs=["Unchanged", "Continued"], requests=[])
    exporter = FakeExporter(calls=[])
    probe = FakeProbe(calls=[])
    pipeline = PipelineFacade(
        recognizer=recognizer,
        translator=translator,
        exporter=exporter,
        media_probe=probe,
    )
    project = Project(
        audio_path=str(audio_path),
        image_path=str(image_path),
        script_path=None,
        cues=[],
        settings={"display_mode": "zh"},
    )

    artifacts = pipeline.run(project=project, output_path=output_path)
    reopened = load_project(artifacts.project_path)

    assert probe.calls == [audio_path]
    assert recognizer.calls == [audio_path]
    assert [request.texts for request in translator.requests] == [["そのまま", "続き"]]
    assert [cue.japanese_script for cue in reopened.cues] == ["", ""]
    assert [cue.japanese_recognized for cue in reopened.cues] == ["そのまま", "続き"]
    assert [cue.chinese for cue in reopened.cues] == ["Unchanged", "Continued"]
    assert [cue.source for cue in reopened.cues] == ["asr", "asr"]
