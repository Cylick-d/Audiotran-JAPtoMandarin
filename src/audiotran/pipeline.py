from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol

from audiotran.domain import Project, SubtitleCue
from audiotran.export import ExportResult, SubtitleStyle, export_video, render_ass, render_srt
from audiotran.io import load_project, read_script, save_project
from audiotran.media import probe_media
from audiotran.subtitles import align_script, segment_text
from audiotran.translation import TranslationRequest

SubtitleMode = Literal["zh", "bilingual"]


class Recognizer(Protocol):
    def transcribe(self, path: Path) -> list[SubtitleCue]:
        ...


class Translator(Protocol):
    def translate(self, request: TranslationRequest) -> list[str]:
        ...


class Exporter(Protocol):
    def __call__(self, audio: Path, image: Path, subtitle_file: Path, output: Path) -> ExportResult:
        ...


@dataclass(slots=True, frozen=True)
class PipelineArtifacts:
    project: Project
    project_path: Path
    srt_path: Path
    ass_path: Path
    export_result: ExportResult


class PipelineFacade:
    def __init__(
        self,
        *,
        recognizer: Recognizer,
        translator: Translator,
        exporter: Exporter = export_video,
        media_probe=probe_media,
        script_loader=read_script,
        project_loader=load_project,
        project_saver=save_project,
    ) -> None:
        self._recognizer = recognizer
        self._translator = translator
        self._exporter = exporter
        self._media_probe = media_probe
        self._script_loader = script_loader
        self._project_loader = project_loader
        self._project_saver = project_saver

    def new_project(self) -> Project:
        return Project(
            audio_path="",
            image_path="",
            script_path=None,
            cues=[],
            settings={"display_mode": "zh"},
        )

    def open_project(self, path: Path) -> Project:
        return self._project_loader(Path(path))

    def save_project(self, project: Project, path: Path) -> None:
        self._project_saver(project, Path(path))

    def load_script(self, path: Path) -> str:
        return self._script_loader(Path(path))

    def transcribe(self, path: Path) -> list[SubtitleCue]:
        return self._recognizer.transcribe(Path(path))

    def align_script(self, project: Project, script_text: str) -> Project:
        updated = self._copy_project(project)
        updated.cues = align_script(segment_text(script_text), self.transcribe(Path(updated.audio_path)))
        return updated

    def align_project(self, project: Project) -> Project:
        if not project.script_path:
            raise ValueError("a script path is required for alignment")
        return self.align_script(project, self.load_script(Path(project.script_path)))

    def build_cues(self, project: Project) -> Project:
        updated = self._copy_project(project)
        if updated.script_path:
            return self.align_project(updated)
        updated.cues = self.transcribe(Path(updated.audio_path))
        return updated

    def translate_project(
        self,
        project: Project,
        *,
        glossary: dict[str, str] | None = None,
    ) -> Project:
        texts = [cue.japanese_script or cue.japanese_recognized for cue in project.cues]
        translations = self._translator.translate(
            TranslationRequest(texts=texts, glossary=dict(glossary or {}))
        )
        if len(translations) != len(project.cues):
            raise ValueError("translator returned an unexpected result")

        updated = self._copy_project(project)
        for cue, chinese in zip(updated.cues, translations):
            cue.chinese = chinese
        return updated

    def export_project(
        self,
        project: Project,
        mode: SubtitleMode | None = None,
        output_path: Path | None = None,
        style: SubtitleStyle | None = None,
    ) -> PipelineArtifacts:
        if output_path is None:
            raise ValueError("an output path is required")
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        subtitle_mode = self._resolve_mode(project, mode)
        subtitle_style = style or self._default_style()

        project_path = destination.with_suffix(".json")
        srt_path = destination.with_suffix(".srt")
        ass_path = destination.with_suffix(".ass")

        self._project_saver(project, project_path)
        srt_path.write_text(render_srt(project.cues, subtitle_mode), encoding="utf-8")
        ass_path.write_text(render_ass(project.cues, subtitle_mode, subtitle_style), encoding="utf-8")
        export_result = self._exporter(
            Path(project.audio_path),
            Path(project.image_path),
            ass_path,
            destination,
        )
        return PipelineArtifacts(
            project=self._copy_project(project),
            project_path=project_path,
            srt_path=srt_path,
            ass_path=ass_path,
            export_result=export_result,
        )

    def run(
        self,
        *,
        project: Project,
        output_path: Path,
        mode: SubtitleMode | None = None,
        glossary: dict[str, str] | None = None,
        style: SubtitleStyle | None = None,
    ) -> PipelineArtifacts:
        audio_path = Path(project.audio_path)
        self._media_probe(audio_path)
        processed = self.build_cues(project)
        translated = self.translate_project(processed, glossary=glossary)
        return self.export_project(
            translated,
            mode=mode,
            output_path=Path(output_path),
            style=style,
        )

    def _copy_project(self, project: Project) -> Project:
        return Project(
            audio_path=project.audio_path,
            image_path=project.image_path,
            script_path=project.script_path,
            cues=[replace(cue) for cue in project.cues],
            settings=dict(project.settings),
        )

    def _resolve_mode(self, project: Project, mode: SubtitleMode | None) -> SubtitleMode:
        if mode is not None:
            return mode
        return "bilingual" if project.settings.get("display_mode") == "bilingual" else "zh"

    def _default_style(self) -> SubtitleStyle:
        return SubtitleStyle(
            font_name="Arial",
            font_size=42,
            primary_color="&H00FFFFFF",
            outline_color="&H00000000",
            back_color="&H00000000",
        )
