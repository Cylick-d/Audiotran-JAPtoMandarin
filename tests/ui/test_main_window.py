from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QRadioButton, QSplitter, QWidget

from audiotran.app import create_application


class DummyProjectService:
    def new_project(self):
        return None

    def open_project(self, path: Path):
        return path

    def save_project(self, project, path: Path):
        return (project, path)

    def load_script(self, path: Path):
        return path.read_text(encoding="utf-8")


class DummyRecognitionService:
    def align_script(self, project):
        return project

    def transcribe(self, path: Path):
        return path


class DummyTranslationService:
    def translate_project(self, project):
        return project


class DummyExportService:
    def export_project(self, project, mode: str):
        return (project, mode)


def build_window():
    from audiotran.ui.main_window import MainWindow

    create_application(["audiotran-ui-test"])
    window = MainWindow(
        project_service=DummyProjectService(),
        recognition_service=DummyRecognitionService(),
        translation_service=DummyTranslationService(),
        export_service=DummyExportService(),
    )
    return window


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
