from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audiotran.domain import Project, SubtitleCue
from audiotran.export import SubtitleStyle, render_ass, render_srt
from audiotran.io.project_store import load_project, save_project
from audiotran.io.script_reader import read_script
from audiotran.subtitles import align_script, segment_text, split_long_cue
from audiotran.translation import TranslationRequest

from .widgets import PreviewPanel, ProjectPanel, SubtitleTable
from .workers import ProjectWorker, WorkerResult


class MainWindow(QMainWindow):
    cuePlaybackRequested = Signal(float, float)

    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    SCRIPT_EXTENSIONS = {".txt"}

    def __init__(
        self,
        project_service,
        recognition_service,
        translation_service,
        export_service,
    ) -> None:
        super().__init__()
        self.project_service = project_service
        self.recognition_service = recognition_service
        self.translation_service = translation_service
        self.export_service = export_service

        self.project = self._empty_project()
        self.current_project_path: Path | None = None
        self.last_successful_stage: str | None = None
        self._script_text: str = ""
        self._worker_thread: QThread | None = None
        self._worker: ProjectWorker | None = None
        self._table_refreshing = False

        self.setWindowTitle("audiotran")
        self.resize(1280, 760)

        self.project_panel = ProjectPanel()
        self.subtitle_table = SubtitleTable()
        self.preview_panel = PreviewPanel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)

        self._build_layout()
        self._connect_signals()
        self._refresh_project_view()
        self._set_status("Ready")

    def _build_layout(self) -> None:
        splitter = QSplitter()
        splitter.setObjectName("workspace-splitter")
        splitter.addWidget(self.project_panel)
        splitter.addWidget(self._build_subtitle_pane())
        splitter.addWidget(self.preview_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.setCentralWidget(splitter)

        status_bar = QStatusBar()
        status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(status_bar)

    def _build_subtitle_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("subtitle-pane")

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        self.split_button = QPushButton("Split Cue")
        self.split_button.setObjectName("split-cue-button")
        self.merge_button = QPushButton("Merge Cues")
        self.merge_button.setObjectName("merge-cues-button")
        self.play_button = QPushButton("Play Cue")
        self.play_button.setObjectName("play-cue-button")
        controls.addWidget(self.split_button)
        controls.addWidget(self.merge_button)
        controls.addWidget(self.play_button)
        controls.addStretch(1)

        layout.addLayout(controls)
        layout.addWidget(self.subtitle_table, 1)
        return pane

    def _connect_signals(self) -> None:
        self.project_panel.new_button.clicked.connect(self.new_project)
        self.project_panel.open_button.clicked.connect(self.open_project_dialog)
        self.project_panel.save_button.clicked.connect(self.save_project_dialog)
        self.project_panel.audio_button.clicked.connect(self.import_audio_dialog)
        self.project_panel.image_button.clicked.connect(self.import_image_dialog)
        self.project_panel.script_button.clicked.connect(self.import_script_dialog)
        self.project_panel.align_button.clicked.connect(self.run_script_alignment)
        self.project_panel.asr_button.clicked.connect(self.run_asr)
        self.project_panel.translate_button.clicked.connect(self.run_translation)

        self.preview_panel.zh_mode_button.toggled.connect(self._update_display_mode)
        self.preview_panel.bilingual_mode_button.toggled.connect(self._update_display_mode)
        self.preview_panel.export_button.clicked.connect(self.export_project_dialog)

        self.subtitle_table.itemChanged.connect(self._handle_item_changed)
        self.subtitle_table.itemSelectionChanged.connect(self._update_preview)

        self.split_button.clicked.connect(self.split_selected_cue)
        self.merge_button.clicked.connect(self.merge_selected_cues)
        self.play_button.clicked.connect(self.play_current_cue)

    def _empty_project(self) -> Project:
        return Project(
            audio_path="",
            image_path="",
            script_path=None,
            cues=[],
            settings={"display_mode": "zh"},
        )

    def new_project(self) -> None:
        created = self._call_if_available(self.project_service, "new_project")
        self.project = created if isinstance(created, Project) else self._empty_project()
        self.current_project_path = None
        self._script_text = ""
        self.last_successful_stage = None
        self._refresh_project_view()
        self._set_status("Started a new project")

    def open_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "Project Files (*.json)",
        )
        if path:
            self.open_project(Path(path))

    def open_project(self, path: Path) -> None:
        project = self._call_if_available(self.project_service, "open_project", path)
        if not isinstance(project, Project):
            project = load_project(path)
        self.project = project
        self.current_project_path = Path(path)
        self._script_text = self._load_script_text_if_available()
        self._apply_display_mode(self._display_mode())
        self._refresh_project_view()
        self._set_status(f"Opened project {Path(path).name}")

    def save_project_dialog(self) -> None:
        if self.current_project_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                "",
                "Project Files (*.json)",
            )
            if not path:
                return
            self.current_project_path = Path(path)
        self.save_project(self.current_project_path)

    def save_project(self, path: Path | None) -> None:
        if path is None:
            raise ValueError("a project save path is required")
        if self._has_callable(self.project_service, "save_project"):
            self._call_if_available(self.project_service, "save_project", self.project, Path(path))
        else:
            save_project(self.project, Path(path))
        self.current_project_path = Path(path)
        self._set_status(f"Saved project {Path(path).name}")

    def import_audio_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Audio",
            "",
            "Audio Files (*.wav *.mp3 *.m4a)",
        )
        if path:
            self.set_audio_path(Path(path))

    def import_image_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Image",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp)",
        )
        if path:
            self.set_image_path(Path(path))

    def import_script_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Script",
            "",
            "Text Files (*.txt)",
        )
        if path:
            self.set_script_path(Path(path))

    def set_audio_path(self, path: Path) -> bool:
        if not self._validate_extension(path, self.AUDIO_EXTENSIONS, "audio"):
            return False
        self.project.audio_path = str(path)
        self._refresh_project_view()
        self._set_status(f"Loaded audio {path.name}")
        return True

    def set_image_path(self, path: Path) -> bool:
        if not self._validate_extension(path, self.IMAGE_EXTENSIONS, "image"):
            return False
        self.project.image_path = str(path)
        self._refresh_project_view()
        self._set_status(f"Loaded image {path.name}")
        return True

    def set_script_path(self, path: Path) -> bool:
        if not self._validate_extension(path, self.SCRIPT_EXTENSIONS, "script"):
            return False
        self.project.script_path = str(path)
        self._script_text = self._read_script(path)
        self._refresh_project_view()
        self._set_status(f"Loaded script {path.name}")
        return True

    def run_script_alignment(self) -> None:
        if not self.project.script_path:
            self._set_status("Import a script before running alignment")
            return
        if not self.project.cues:
            self._set_status("Run ASR before aligning a script")
            return

        script_text = self._script_text or self._read_script(Path(self.project.script_path))
        self._start_worker("alignment", lambda worker: self._align_in_worker(worker, script_text), self._apply_project_result)

    def run_asr(self) -> None:
        if not self.project.audio_path:
            self._set_status("Import audio before running ASR")
            return
        self._start_worker("asr", self._transcribe_in_worker, self._apply_project_result)

    def run_translation(self) -> None:
        if not self.project.cues:
            self._set_status("Create subtitle cues before translating")
            return
        self._start_worker("translation", self._translate_in_worker, self._apply_project_result)

    def export_project_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            "",
            "Video Files (*.mp4)",
        )
        if path:
            self.export_project(Path(path))

    def export_project(self, output_path: Path) -> None:
        if not self.project.audio_path or not self.project.image_path or not self.project.cues:
            self._set_status("Import audio, image, and subtitles before exporting")
            return
        self._start_worker(
            "export",
            lambda worker: self._export_in_worker(worker, output_path),
            self._handle_export_result,
        )

    def split_selected_cue(self) -> None:
        row = self.subtitle_table.currentRow()
        if row < 0 or row >= len(self.project.cues):
            self._set_status("Select one cue to split")
            return

        cue = self.project.cues[row]
        replacement = split_long_cue(cue)
        self.project.cues[row : row + 1] = replacement
        self._reindex_cues()
        self._refresh_project_view()
        self.subtitle_table.selectRow(row)
        self._set_status("Split the selected cue")

    def merge_selected_cues(self) -> None:
        rows = sorted({index.row() for index in self.subtitle_table.selectedIndexes()})
        if len(rows) < 2:
            self._set_status("Select two or more cues to merge")
            return
        if rows != list(range(rows[0], rows[-1] + 1)):
            self._set_status("Select adjacent cues to merge them")
            return

        selected = [self.project.cues[row] for row in rows]
        merged = SubtitleCue(
            id=selected[0].id,
            start=selected[0].start,
            end=selected[-1].end,
            japanese_script="".join(cue.japanese_script for cue in selected),
            japanese_recognized="".join(cue.japanese_recognized for cue in selected),
            chinese="".join(cue.chinese for cue in selected),
            confidence=min((cue.confidence for cue in selected if cue.confidence is not None), default=None),
            source=selected[0].source,
            reviewed=all(cue.reviewed for cue in selected),
        )
        self.project.cues[rows[0] : rows[-1] + 1] = [merged]
        self._reindex_cues()
        self._refresh_project_view()
        self.subtitle_table.selectRow(rows[0])
        self._set_status("Merged the selected cues")

    def play_current_cue(self) -> None:
        row = self.subtitle_table.currentRow()
        if row < 0 or row >= len(self.project.cues):
            self._set_status("Select a cue to preview it")
            return
        cue = self.project.cues[row]
        self.cuePlaybackRequested.emit(cue.start, cue.end)
        self._set_status(f"Previewing cue {cue.id}")

    def _start_worker(self, stage: str, task, on_success) -> None:
        if self._worker_thread is not None:
            self._set_status("Wait for the current task to finish")
            return

        thread = QThread(self)
        worker = ProjectWorker(stage=stage, task=task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._update_progress)
        worker.result.connect(lambda outcome: self._handle_worker_result(outcome, on_success))
        worker.error.connect(lambda message, current_stage=stage: self._handle_worker_error(current_stage, message))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, stage)
        thread.start()

    def _clear_worker(self) -> None:
        self._worker_thread = None
        self._worker = None
        self._set_busy(False, None)

    def _handle_worker_result(self, outcome: WorkerResult, on_success) -> None:
        if outcome.error_message:
            return
        self.last_successful_stage = outcome.stage
        on_success(outcome.payload)
        self._set_status(f"Completed {outcome.stage}")

    def _handle_worker_error(self, stage: str, message: str) -> None:
        self._set_status(f"{stage} failed: {message}")

    def _update_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self._set_status(message)

    def _set_busy(self, busy: bool, stage: str | None) -> None:
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setValue(0)
            self._set_status(f"Running {stage}")
        for button in (
            self.project_panel.align_button,
            self.project_panel.asr_button,
            self.project_panel.translate_button,
            self.preview_panel.export_button,
        ):
            button.setEnabled(not busy)

    def _transcribe_in_worker(self, worker: ProjectWorker) -> Project:
        worker.report_progress(10, "Running speech recognition")
        transcribe = getattr(self.recognition_service, "transcribe")
        result = transcribe(Path(self.project.audio_path))
        worker.report_progress(90, "Applying speech recognition output")

        if isinstance(result, Project):
            return result
        project = self._clone_project()
        project.cues = result if isinstance(result, list) else list(project.cues)
        for cue in project.cues:
            cue.source = "asr"
        return project

    def _align_in_worker(self, worker: ProjectWorker, script_text: str) -> Project:
        worker.report_progress(10, "Segmenting script")
        service_method = getattr(self.recognition_service, "align_script", None)
        project = self._clone_project()
        if callable(service_method):
            result = self._call_service_method(service_method, project, script_text)
            if isinstance(result, Project):
                return result
            if isinstance(result, list):
                project.cues = result
                return project

        script_segments = segment_text(script_text)
        worker.report_progress(60, "Aligning recognized text with script")
        project.cues = align_script(script_segments, project.cues)
        return project

    def _translate_in_worker(self, worker: ProjectWorker) -> Project:
        worker.report_progress(10, "Translating subtitle cues")
        project = self._clone_project()

        service_method = getattr(self.translation_service, "translate_project", None)
        if callable(service_method):
            result = self._call_service_method(service_method, project)
            if isinstance(result, Project):
                return result

        texts = [cue.japanese_script or cue.japanese_recognized for cue in project.cues]
        translator = getattr(self.translation_service, "translate", None)
        if not callable(translator):
            raise ValueError("translation service does not provide a translate operation")

        translations = self._call_service_method(translator, TranslationRequest(texts=texts))
        if not isinstance(translations, list) or len(translations) != len(project.cues):
            raise ValueError("translation service returned an unexpected result")
        for cue, chinese in zip(project.cues, translations):
            cue.chinese = chinese
        worker.report_progress(90, "Applied translations")
        return project

    def _export_in_worker(self, worker: ProjectWorker, output_path: Path):
        worker.report_progress(10, "Preparing subtitle export")
        mode = self._display_mode()

        service_method = getattr(self.export_service, "export_project", None)
        if callable(service_method):
            return self._call_service_method(service_method, self._clone_project(), mode, output_path)

        fallback = getattr(self.export_service, "export", None)
        if callable(fallback):
            return self._call_service_method(fallback, self._clone_project(), mode, output_path)

        style = SubtitleStyle(
            font_name="Arial",
            font_size=42,
            primary_color="&H00FFFFFF",
            outline_color="&H00000000",
            back_color="&H00000000",
        )
        subtitles = {
            "srt": render_srt(self.project.cues, mode),
            "ass": render_ass(self.project.cues, mode, style),
            "output_path": str(output_path),
        }
        worker.report_progress(90, "Prepared subtitle files for export")
        return subtitles

    def _apply_project_result(self, payload) -> None:
        if isinstance(payload, Project):
            self.project = payload
        self._refresh_project_view()

    def _handle_export_result(self, _payload) -> None:
        self._set_status("Export finished")

    def _refresh_project_view(self) -> None:
        self.project_panel.set_paths(
            self.project.audio_path,
            self.project.image_path,
            self.project.script_path,
        )
        self._refresh_table()
        self._apply_display_mode(self._display_mode())
        self._update_preview()

    def _refresh_table(self) -> None:
        self._table_refreshing = True
        try:
            self.subtitle_table.set_cues(self.project.cues)
        finally:
            self._table_refreshing = False

    def _update_display_mode(self) -> None:
        mode = "bilingual" if self.preview_panel.bilingual_mode_button.isChecked() else "zh"
        self.project.settings["display_mode"] = mode
        self._update_preview()

    def _apply_display_mode(self, mode: str) -> None:
        if mode == "bilingual":
            self.preview_panel.bilingual_mode_button.setChecked(True)
        else:
            self.preview_panel.zh_mode_button.setChecked(True)

    def _display_mode(self) -> str:
        stored = self.project.settings.get("display_mode", "zh")
        return "bilingual" if stored == "bilingual" else "zh"

    def _handle_item_changed(self, item: QTableWidgetItem) -> None:
        if self._table_refreshing:
            return
        row = item.row()
        column = item.column()
        if row < 0 or row >= len(self.project.cues):
            return

        cue = self.project.cues[row]
        if column == 2:
            cue.japanese_script = item.text()
        elif column == 3:
            cue.japanese_recognized = item.text()
        elif column == 4:
            cue.chinese = item.text()
        elif column == 6:
            cue.reviewed = item.checkState() == Qt.CheckState.Checked
        self._update_preview()

    def _update_preview(self) -> None:
        rows = sorted({index.row() for index in self.subtitle_table.selectedIndexes()})
        cues = [self.project.cues[row] for row in rows if 0 <= row < len(self.project.cues)]
        if not cues:
            cues = self.project.cues

        mode = self._display_mode()
        chunks = [self._render_cue_preview(cue, mode) for cue in cues]
        self.preview_panel.set_preview_text("\n\n".join(chunk for chunk in chunks if chunk))

    def _render_cue_preview(self, cue: SubtitleCue, mode: str) -> str:
        source_text = cue.japanese_script or cue.japanese_recognized
        chinese = cue.chinese or source_text
        if mode == "bilingual":
            return f"{chinese}\n{source_text}".strip()
        return chinese

    def _validate_extension(self, path: Path, allowed: set[str], label: str) -> bool:
        if path.suffix.lower() not in allowed:
            extensions = ", ".join(sorted(allowed))
            self._set_status(f"Unsupported {label} file type. Use: {extensions}")
            return False
        return True

    def _set_status(self, message: str) -> None:
        self.preview_panel.set_status(message)
        self.statusBar().showMessage(message)

    def _clone_project(self) -> Project:
        return Project(
            audio_path=self.project.audio_path,
            image_path=self.project.image_path,
            script_path=self.project.script_path,
            cues=[replace(cue) for cue in self.project.cues],
            settings=dict(self.project.settings),
        )

    def _read_script(self, path: Path) -> str:
        result = self._call_if_available(self.project_service, "load_script", path)
        if isinstance(result, str):
            return result
        return read_script(path)

    def _load_script_text_if_available(self) -> str:
        if not self.project.script_path:
            return ""
        path = Path(self.project.script_path)
        if not path.exists():
            return ""
        return self._read_script(path)

    def _reindex_cues(self) -> None:
        for index, cue in enumerate(self.project.cues, start=1):
            cue.id = index

    def _call_if_available(self, service, name: str, *args):
        method = getattr(service, name, None)
        if callable(method):
            return self._call_service_method(method, *args)
        return None

    def _has_callable(self, service, name: str) -> bool:
        return callable(getattr(service, name, None))

    def _call_service_method(self, method, *args):
        signature = inspect.signature(method)
        parameters = list(signature.parameters.values())
        if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
            return method(*args)
        positional_capacity = len(
            [
                parameter
                for parameter in parameters
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
        )
        return method(*args[:positional_capacity])
