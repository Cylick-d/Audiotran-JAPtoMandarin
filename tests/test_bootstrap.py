def test_package_imports():
    import audiotran

    assert audiotran.__version__


def test_create_application_returns_qapplication():
    from PySide6.QtWidgets import QApplication

    from audiotran.app import create_application

    app = create_application(["audiotran-test"])

    assert isinstance(app, QApplication)
    assert QApplication.instance() is app


def test_configure_qt_platform_only_for_test_runs():
    from audiotran.app import _configure_qt_platform

    runtime_env: dict[str, str] = {}
    test_env: dict[str, str] = {"PYTEST_CURRENT_TEST": "tests/test_bootstrap.py::test"}

    _configure_qt_platform(runtime_env)
    _configure_qt_platform(test_env)

    assert "QT_QPA_PLATFORM" not in runtime_env
    assert test_env["QT_QPA_PLATFORM"] == "offscreen"


def test_create_main_window_returns_window_with_real_workspace_shell():
    from pathlib import Path

    from audiotran.app import create_main_window
    from audiotran.domain import Project

    class FakePipeline:
        def new_project(self) -> Project:
            return Project(audio_path="", image_path="", script_path=None, cues=[], settings={})

        def open_project(self, path: Path) -> Project:
            raise FileNotFoundError(path)

        def save_project(self, project: Project, path: Path) -> None:
            return None

        def load_script(self, path: Path) -> str:
            return path.read_text(encoding="utf-8")

        def transcribe(self, path: Path):
            return []

        def align_script(self, project: Project, script_text: str) -> Project:
            return project

        def translate_project(self, project: Project) -> Project:
            return project

        def export_project(self, project: Project, mode: str, output_path: Path):
            return {"video": output_path}

    window = create_main_window(["audiotran-test"], pipeline=FakePipeline())

    assert window.windowTitle() == "audiotran"
    window.close()
    window.deleteLater()
