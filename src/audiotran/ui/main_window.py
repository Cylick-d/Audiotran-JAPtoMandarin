from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal, Slot
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
        self._project_revision = 0
        self._active_worker_revision: int | None = None

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

    @Slot()
    def new_project(self) -> None:
        try:
            created = self.project_service.new_project()
        except (OSError, ValueError) as exc:
            self._set_status(f"Failed to create project: {exc}")
            return
        self.project = created if isinstance(created, Project) else self._empty_project()
        self.current_project_path = None
        self._script_text = ""
        self.last_successful_stage = None
        self._mark_project_changed()
        self._refresh_project_view()
        self._set_status("Started a new project")

    @Slot()
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
        try:
            project = self.project_service.open_project(Path(path))
        except (OSError, ValueError) as exc:
            self._set_status(f"Failed to open project: {exc}")
            return

        self.project = project
        self.current_project_path = Path(path)
        self._script_text = ""
        self.last_successful_stage = None
        self._mark_project_changed()
        self._refresh_project_view()
        try:
            self._script_text = self._load_script_text(project.script_path)
        except (OSError, ValueError) as exc:
            self._set_status(f"Opened project {Path(path).name}; script unavailable: {exc}")
            return
        self._set_status(f"Opened project {Path(path).name}")

    @Slot()
    def save_project_dialog(self) -> None:
        save_path = self.current_project_path
        if save_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                "",
                "Project Files (*.json)",
            )
            if not path:
                return
            save_path = Path(path)
        self.save_project(save_path)

    def save_project(self, path: Path | None) -> None:
        if path is None:
            raise ValueError("a project save path is required")
        try:
            self.project_service.save_project(self.project, Path(path))
        except (OSError, ValueError) as exc:
            self._set_status(f"Failed to save project: {exc}")
            return
        self.current_project_path = Path(path)
        self._set_status(f"Saved project {Path(path).name}")

    @Slot()
    def import_audio_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Audio",
            "",
            "Audio Files (*.wav *.mp3 *.m4a)",
        )
        if path:
            self.set_audio_path(Path(path))

    @Slot()
    def import_image_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Image",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp)",
        )
        if path:
            self.set_image_path(Path(path))

    @Slot()
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
        self._mark_project_changed()
        self._refresh_project_view()
        self._set_status(f"Loaded audio {path.name}")
        return True

    def set_image_path(self, path: Path) -> bool:
        if not self._validate_extension(path, self.IMAGE_EXTENSIONS, "image"):
            return False
        self.project.image_path = str(path)
        self._mark_project_changed()
        self._refresh_project_view()
        self._set_status(f"Loaded image {path.name}")
        return True

    def set_script_path(self, path: Path) -> bool:
        if not self._validate_extension(path, self.SCRIPT_EXTENSIONS, "script"):
            return False
        try:
            script_text = self.project_service.load_script(Path(path))
        except (OSError, ValueError) as exc:
            self._set_status(f"Failed to load script: {exc}")
            return False

        self.project.script_path = str(path)
        self._script_text = script_text
        self._mark_project_changed()
        self._refresh_project_view()
        self._set_status(f"Loaded script {path.name}")
        return True

    @Slot()
    def run_script_alignment(self) -> None:
        if not self.project.script_path:
            self._set_status("Import a script before running alignment")
            return
        if not self.project.cues:
            self._set_status("Run ASR before aligning a script")
            return
        try:
            script_text = self._script_text or self.project_service.load_script(Path(self.project.script_path))
        except (OSError, ValueError) as exc:
            self._set_status(f"Failed to load script: {exc}")
            return

        project_snapshot = self._snapshot_project()
        self._start_worker(
            "alignment",
            project_snapshot,
            lambda worker, snapshot=project_snapshot, text=script_text: self._align_in_worker(
                worker,
                snapshot,
                text,
            ),
        )

    @Slot()
    def run_asr(self) -> None:
        if not self.project.audio_path:
            self._set_status("Import audio before running ASR")
            return
        project_snapshot = self._snapshot_project()
        self._start_worker(
            "asr",
            project_snapshot,
            lambda worker, snapshot=project_snapshot: self._transcribe_in_worker(worker, snapshot),
        )

    @Slot()
    def run_translation(self) -> None:
        if not self.project.cues:
            self._set_status("Create subtitle cues before translating")
            return
        project_snapshot = self._snapshot_project()
        self._start_worker(
            "translation",
            project_snapshot,
            lambda worker, snapshot=project_snapshot: self._translate_in_worker(worker, snapshot),
        )

    @Slot()
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
        project_snapshot = self._snapshot_project()
        self._start_worker(
            "export",
            project_snapshot,
            lambda worker, snapshot=project_snapshot, path=Path(output_path): self._export_in_worker(
                worker,
                snapshot,
                path,
            ),
        )

    @Slot()
    def split_selected_cue(self) -> None:
        row = self.subtitle_table.currentRow()
        if row < 0 or row >= len(self.project.cues):
            self._set_status("Select one cue to split")
            return

        cue = self.project.cues[row]
        replacement = split_long_cue(cue)
        self.project.cues[row : row + 1] = replacement
        self._reindex_cues()
        self._mark_project_changed()
        self._refresh_project_view()
        self.subtitle_table.selectRow(row)
        self._set_status("Split the selected cue")

    @Slot()
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
            confidence=min(
                (cue.confidence for cue in selected if cue.confidence is not None),
                default=None,
            ),
            source=selected[0].source,
            reviewed=all(cue.reviewed for cue in selected),
        )
        self.project.cues[rows[0] : rows[-1] + 1] = [merged]
        self._reindex_cues()
        self._mark_project_changed()
        self._refresh_project_view()
        self.subtitle_table.selectRow(rows[0])
        self._set_status("Merged the selected cues")

    @Slot()
    def play_current_cue(self) -> None:
        row = self.subtitle_table.currentRow()
        if row < 0 or row >= len(self.project.cues):
            self._set_status("Select a cue to preview it")
            return
        cue = self.project.cues[row]
        self.cuePlaybackRequested.emit(cue.start, cue.end)
        self._set_status(f"Previewing cue {cue.id}")

    def _start_worker(self, stage: str, project_snapshot: Project, task) -> None:
        if self._worker_thread is not None:
            self._set_status("Wait for the current task to finish")
            return

        request_revision = self._project_revision
        thread = QThread(self)
        worker = ProjectWorker(stage=stage, request_revision=request_revision, task=task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._update_progress, Qt.ConnectionType.QueuedConnection)
        worker.result.connect(self._on_worker_result, Qt.ConnectionType.QueuedConnection)
        worker.error.connect(self._on_worker_error, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._worker_thread = thread
        self._worker = worker
        self._active_worker_revision = request_revision
        self._set_busy(True, stage)
        thread.start()

    @Slot(object)
    def _on_worker_result(self, outcome: WorkerResult) -> None:
        if outcome.request_revision != self._active_worker_revision:
            self._set_status(f"Ignored stale {outcome.stage} result")
            return
        if outcome.request_revision != self._project_revision:
            self._set_status(f"Ignored stale {outcome.stage} result")
            return

        if outcome.stage == "export":
            self._handle_export_result(outcome.payload)
        else:
            self._apply_project_result(outcome.payload)
        self.last_successful_stage = outcome.stage
        self._set_status(f"Completed {outcome.stage}")

    @Slot(object)
    def _on_worker_error(self, outcome: WorkerResult) -> None:
        message = outcome.error_message or "worker failed"
        self._set_status(f"{outcome.stage} failed: {message}")

    @Slot()
    def _on_worker_finished(self) -> None:
        self._worker_thread = None
        self._worker = None
        self._active_worker_revision = None
        self._set_busy(False, None)

    @Slot(int, str)
    def _update_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self._set_status(message)

    def _set_busy(self, busy: bool, stage: str | None) -> None:
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setValue(0)
            self._set_status(f"Running {stage}")

        for widget in (
            self.project_panel.new_button,
            self.project_panel.open_button,
            self.project_panel.save_button,
            self.project_panel.audio_button,
            self.project_panel.image_button,
            self.project_panel.script_button,
            self.project_panel.align_button,
            self.project_panel.asr_button,
            self.project_panel.translate_button,
            self.preview_panel.zh_mode_button,
            self.preview_panel.bilingual_mode_button,
            self.preview_panel.export_button,
            self.subtitle_table,
            self.split_button,
            self.merge_button,
            self.play_button,
        ):
            widget.setEnabled(not busy)

    def _transcribe_in_worker(self, worker: ProjectWorker, project_snapshot: Project) -> Project:
        worker.report_progress(10, "Running speech recognition")
        result = self.recognition_service.transcribe(Path(project_snapshot.audio_path))
        worker.report_progress(90, "Applying speech recognition output")

        if isinstance(result, Project):
            return result

        project = self._snapshot_project(project_snapshot)
        project.cues = result if isinstance(result, list) else list(project.cues)
        for cue in project.cues:
            cue.source = "asr"
        return project

    def _align_in_worker(
        self,
        worker: ProjectWorker,
        project_snapshot: Project,
        script_text: str,
    ) -> Project:
        worker.report_progress(10, "Segmenting script")
        result = self.recognition_service.align_script(project_snapshot, script_text)
        if isinstance(result, Project):
            worker.report_progress(90, "Applied aligned script")
            return result
        if isinstance(result, list):
            project = self._snapshot_project(project_snapshot)
            project.cues = result
            worker.report_progress(90, "Applied aligned script")
            return project

        script_segments = segment_text(script_text)
        worker.report_progress(60, "Aligning recognized text with script")
        project = self._snapshot_project(project_snapshot)
        project.cues = align_script(script_segments, project.cues)
        return project

    def _translate_in_worker(self, worker: ProjectWorker, project_snapshot: Project) -> Project:
        worker.report_progress(10, "Translating subtitle cues")
        result = self.translation_service.translate_project(project_snapshot)
        if isinstance(result, Project):
            worker.report_progress(90, "Applied translations")
            return result

        texts = [cue.japanese_script or cue.japanese_recognized for cue in project_snapshot.cues]
        translations = self.translation_service.translate(TranslationRequest(texts=texts))
        if len(translations) != len(project_snapshot.cues):
            raise ValueError("translation service returned an unexpected result")

        project = self._snapshot_project(project_snapshot)
        for cue, chinese in zip(project.cues, translations):
            cue.chinese = chinese
        worker.report_progress(90, "Applied translations")
        return project

    def _export_in_worker(
        self,
        worker: ProjectWorker,
        project_snapshot: Project,
        output_path: Path,
    ):
        worker.report_progress(10, "Preparing subtitle export")
        mode = self._display_mode(project_snapshot)
        result = self.export_service.export_project(project_snapshot, mode, output_path)
        if result is not None:
            worker.report_progress(90, "Prepared export output")
            return result

        style = SubtitleStyle(
            font_name="Arial",
            font_size=42,
            primary_color="&H00FFFFFF",
            outline_color="&H00000000",
            back_color="&H00000000",
        )
        subtitles = {
            "srt": render_srt(project_snapshot.cues, mode),
            "ass": render_ass(project_snapshot.cues, mode, style),
            "output_path": str(output_path),
        }
        worker.report_progress(90, "Prepared subtitle files for export")
        return subtitles

    def _apply_project_result(self, payload: object | None) -> None:
        if isinstance(payload, Project):
            self.project = payload
            self._mark_project_changed()
        self._refresh_project_view()

    def _handle_export_result(self, _payload: object | None) -> None:
        self._set_status("Export finished")

    def _refresh_project_view(self) -> None:
        self.project_panel.set_paths(
            self.project.audio_path,
            self.project.image_path,
            self.project.script_path,
        )
        self._refresh_table()
        self._apply_display_mode(self._display_mode(self.project))
        self._update_preview()

    def _refresh_table(self) -> None:
        self._table_refreshing = True
        try:
            self.subtitle_table.set_cues(self.project.cues)
        finally:
            self._table_refreshing = False

    @Slot()
    def _update_display_mode(self) -> None:
        mode = "bilingual" if self.preview_panel.bilingual_mode_button.isChecked() else "zh"
        if self.project.settings.get("display_mode") != mode:
            self.project.settings["display_mode"] = mode
            self._mark_project_changed()
        self._update_preview()

    def _apply_display_mode(self, mode: str) -> None:
        if mode == "bilingual":
            self.preview_panel.bilingual_mode_button.setChecked(True)
        else:
            self.preview_panel.zh_mode_button.setChecked(True)

    def _display_mode(self, project: Project) -> str:
        stored = project.settings.get("display_mode", "zh")
        return "bilingual" if stored == "bilingual" else "zh"

    @Slot(QTableWidgetItem)
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
        else:
            return
        self._mark_project_changed()
        self._update_preview()

    @Slot()
    def _update_preview(self) -> None:
        rows = sorted({index.row() for index in self.subtitle_table.selectedIndexes()})
        cues = [self.project.cues[row] for row in rows if 0 <= row < len(self.project.cues)]
        if not cues:
            cues = self.project.cues

        mode = self._display_mode(self.project)
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

    def _snapshot_project(self, project: Project | None = None) -> Project:
        source = self.project if project is None else project
        return Project(
            audio_path=source.audio_path,
            image_path=source.image_path,
            script_path=source.script_path,
            cues=[replace(cue) for cue in source.cues],
            settings=dict(source.settings),
        )

    def _load_script_text(self, script_path: str | None) -> str:
        if not script_path:
            return ""
        return self.project_service.load_script(Path(script_path))

    def _reindex_cues(self) -> None:
        for index, cue in enumerate(self.project.cues, start=1):
            cue.id = index

    def _mark_project_changed(self) -> None:
        self._project_revision += 1
