from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import threading
import time

import pytest
from PySide6.QtWidgets import QPushButton, QRadioButton, QSplitter

from audiotran.app import create_application
from audiotran.domain import Project, SubtitleCue
from audiotran.io.project_store import load_project, save_project
from audiotran.io.script_reader import ScriptEncodingError
from audiotran.ui.workers import ProjectWorker


def make_cue(
    *,
    cue_id: int = 1,
    japanese_script: str = "script text",
    japanese_recognized: str = "recognized text",
    chinese: str = "chinese text",
    reviewed: bool = False,
) -> SubtitleCue:
    return SubtitleCue(
        id=cue_id,
        start=0.0,
        end=2.0,
        japanese_script=japanese_script,
        japanese_recognized=japanese_recognized,
        chinese=chinese,
        confidence=0.9,
        source="asr",
        reviewed=reviewed,
    )


def make_project(*, cues: list[SubtitleCue] | None = None, script_path: str | None = None) -> Project:
    return Project(
        audio_path="audio.wav",
        image_path="image.png",
        script_path=script_path,
        cues=list(cues or []),
        settings={"display_mode": "zh"},
    )


class FakeProjectService:
    def __init__(self) -> None:
        self.new_project_result: Project | None = None
        self.open_project_error: Exception | None = None
        self.save_project_error: Exception | None = None
        self.load_script_error: Exception | None = None

    def new_project(self) -> Project | None:
        return self.new_project_result

    def open_project(self, path: Path) -> Project:
        if self.open_project_error is not None:
            raise self.open_project_error
        return load_project(path)

    def save_project(self, project: Project, path: Path) -> None:
        if self.save_project_error is not None:
            raise self.save_project_error
        save_project(project, path)

    def load_script(self, path: Path) -> str:
        if self.load_script_error is not None:
            raise self.load_script_error
        return path.read_text(encoding="utf-8")


class FakeRecognitionService:
    def __init__(self) -> None:
        self.transcribe_result: list[SubtitleCue] | Project = [make_cue()]
        self.transcribe_error: Exception | None = None
        self.align_result: Project | list[SubtitleCue] | None = None
        self.align_error: Exception | None = None

    def transcribe(self, path: Path) -> list[SubtitleCue] | Project:
        if self.transcribe_error is not None:
            raise self.transcribe_error
        return self.transcribe_result

    def align_script(self, project: Project, script_text: str) -> Project | list[SubtitleCue]:
        if self.align_error is not None:
            raise self.align_error
        if self.align_result is not None:
            return self.align_result
        cue = replace(project.cues[0], japanese_script=script_text)
        return replace(project, cues=[cue])


class FakeTranslationService:
    def __init__(self) -> None:
        self.received_projects: list[Project] = []
        self.error: Exception | None = None
        self.started_event = threading.Event()
        self.release_event = threading.Event()
        self.block = False

    def translate_project(self, project: Project) -> Project:
        self.received_projects.append(project)
        self.started_event.set()
        if self.block:
            assert self.release_event.wait(timeout=2.0), "worker did not receive release signal"
        if self.error is not None:
            raise self.error
        translated_cues = [
            replace(cue, chinese=f"translated: {cue.japanese_script or cue.japanese_recognized}")
            for cue in project.cues
        ]
        return replace(project, cues=translated_cues)


class FakeExportService:
    def __init__(self) -> None:
        self.calls: list[tuple[Project, str, Path]] = []

    def export_project(self, project: Project, mode: str, output_path: Path):
        self.calls.append((project, mode, output_path))
        return {"video": output_path}


def build_window(
    *,
    project_service: FakeProjectService | None = None,
    recognition_service: FakeRecognitionService | None = None,
    translation_service: FakeTranslationService | None = None,
    export_service: FakeExportService | None = None,
):
    from audiotran.ui.main_window import MainWindow

    create_application(["audiotran-ui-test"])
    window = MainWindow(
        project_service=project_service or FakeProjectService(),
        recognition_service=recognition_service or FakeRecognitionService(),
        translation_service=translation_service or FakeTranslationService(),
        export_service=export_service or FakeExportService(),
    )
    return window


def wait_until(condition, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    app = create_application(["audiotran-ui-test"])
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


@pytest.fixture(autouse=True)
def drain_events_after_test():
    yield
    app = create_application(["audiotran-ui-test"])
    app.processEvents()
    time.sleep(0.02)
    app.processEvents()


def test_main_window_exposes_three_workspace_panes():
    window = build_window()

    splitter = window.findChild(QSplitter, "workspace-splitter")

    assert splitter is not None
    assert splitter.count() == 3
    assert splitter.widget(0).objectName() == "project-pane"
    assert splitter.widget(1).objectName() == "subtitle-pane"
    assert splitter.widget(2).objectName() == "preview-pane"


def test_main_window_exposes_import_and_display_mode_controls():
    window = build_window()

    assert window.findChild(QPushButton, "audio-button") is not None
    assert window.findChild(QPushButton, "image-button") is not None
    assert window.findChild(QPushButton, "script-button") is not None
    assert window.findChild(QRadioButton, "mode-zh") is not None
    assert window.findChild(QRadioButton, "mode-bilingual") is not None


def test_main_window_registers_worker_handlers_as_qobject_slots():
    window = build_window()
    meta_object = window.metaObject()

    assert meta_object.indexOfSlot("_on_worker_result(PyObject)") >= 0
    assert meta_object.indexOfSlot("_on_worker_error(PyObject)") >= 0
    assert meta_object.indexOfSlot("_on_worker_finished()") >= 0
    assert meta_object.indexOfSlot("_update_progress(int,QString)") >= 0


def test_translation_worker_uses_captured_snapshot_and_disables_editing_controls(
    monkeypatch: pytest.MonkeyPatch,
):
    translation_service = FakeTranslationService()
    translation_service.block = True
    window = build_window(translation_service=translation_service)
    window.project = make_project(cues=[make_cue(japanese_script="before busy edit", chinese="before busy edit")])
    window._refresh_project_view()

    snapshot_threads: list[object] = []
    captured_snapshots: list[Project] = []
    original_snapshot = window._snapshot_project

    def record_snapshot(project: Project | None = None) -> Project:
        snapshot_threads.append(window.thread().currentThread())
        snapshot = original_snapshot(project)
        captured_snapshots.append(snapshot)
        return snapshot

    monkeypatch.setattr(window, "_snapshot_project", record_snapshot)

    window.run_translation()
    wait_until(translation_service.started_event.is_set)

    assert not window.subtitle_table.isEnabled()
    assert not window.split_button.isEnabled()
    assert not window.merge_button.isEnabled()
    assert not window.play_button.isEnabled()
    assert snapshot_threads
    assert snapshot_threads[0] == window.thread()
    assert captured_snapshots[0].cues[0].japanese_script == "before busy edit"

    window.project.cues[0].japanese_script = "mutated after worker start"
    translation_service.release_event.set()
    wait_until(lambda: window._worker_thread is None)

    assert translation_service.received_projects[0].cues[0].japanese_script == "before busy edit"
    assert window.subtitle_table.isEnabled()
    assert window.split_button.isEnabled()
    assert window.merge_button.isEnabled()
    assert window.play_button.isEnabled()


def test_translation_worker_error_updates_status_and_releases_busy_controls():
    translation_service = FakeTranslationService()
    translation_service.block = True
    translation_service.error = RuntimeError("translation boom")
    window = build_window(translation_service=translation_service)
    window.project = make_project(cues=[make_cue()])
    window._refresh_project_view()

    window.run_translation()
    wait_until(translation_service.started_event.is_set)

    assert not window.subtitle_table.isEnabled()
    translation_service.release_event.set()
    wait_until(lambda: window._worker_thread is None)

    assert "translation failed: translation boom" in window.statusBar().currentMessage()
    assert window.subtitle_table.isEnabled()


@pytest.mark.parametrize(
    "path_builder",
    [
        lambda tmp_path: tmp_path / "missing.json",
        lambda tmp_path: _write_broken_project(tmp_path / "broken.json"),
    ],
)
def test_open_project_reports_recoverable_error_for_invalid_files(tmp_path: Path, path_builder):
    window = build_window()
    path = path_builder(tmp_path)

    window.open_project(Path(path))

    assert "Failed to open project" in window.statusBar().currentMessage()


def _write_broken_project(path: Path) -> Path:
    path.write_text("{not json", encoding="utf-8")
    return path


def test_open_project_keeps_valid_project_when_script_file_is_missing(tmp_path: Path):
    project_path = tmp_path / "project.json"
    missing_script_path = tmp_path / "missing-script.txt"
    project = make_project(cues=[make_cue()], script_path=str(missing_script_path))
    save_project(project, project_path)
    window = build_window()

    window.open_project(project_path)

    assert window.current_project_path == project_path
    assert window.project.script_path == str(missing_script_path)
    assert window.project.cues[0].japanese_script == "script text"
    assert window._script_text == ""
    assert "Opened project project.json" in window.statusBar().currentMessage()
    assert "script" in window.preview_panel.status_label.text().lower()


def test_save_project_reports_recoverable_error(tmp_path: Path):
    project_service = FakeProjectService()
    project_service.save_project_error = OSError("disk full")
    window = build_window(project_service=project_service)
    window.project = make_project(cues=[make_cue()])

    window.save_project(tmp_path / "project.json")

    assert "Failed to save project" in window.statusBar().currentMessage()


def test_set_script_path_reports_recoverable_encoding_error(tmp_path: Path):
    project_service = FakeProjectService()
    script_path = tmp_path / "script.txt"
    script_path.write_bytes(b"\xff")
    project_service.load_script_error = ScriptEncodingError(script_path)
    window = build_window(project_service=project_service)

    window.set_script_path(script_path)

    assert window.project.script_path is None
    assert "Failed to load script" in window.statusBar().currentMessage()


def test_editing_a_table_cell_updates_project_and_preview():
    window = build_window()
    window.project = make_project(cues=[make_cue(chinese="old chinese")])
    window._refresh_project_view()

    item = window.subtitle_table.item(0, 4)
    item.setText("new chinese")
    wait_until(lambda: window.project.cues[0].chinese == "new chinese")

    assert window.project.cues[0].chinese == "new chinese"
    assert "new chinese" in window.preview_panel.preview_text.toPlainText()


def test_asr_worker_applies_result_and_marks_last_successful_stage():
    recognition_service = FakeRecognitionService()
    recognition_service.transcribe_result = [make_cue(japanese_recognized="from worker", chinese="from worker")]
    window = build_window(recognition_service=recognition_service)
    window.project.audio_path = "voice.wav"

    window.run_asr()
    wait_until(lambda: window._worker_thread is None)

    assert window.last_successful_stage == "asr"
    assert window.project.cues[0].japanese_recognized == "from worker"
    assert "Completed asr" in window.statusBar().currentMessage()
