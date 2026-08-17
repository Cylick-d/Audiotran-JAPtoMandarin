import json
import os
from pathlib import Path
import runpy

import pytest


def test_package_imports():
    import audiotran

    assert audiotran.__version__


def test_packaged_launcher_runs_as_a_top_level_script_without_starting_gui(
    monkeypatch: pytest.MonkeyPatch,
):
    import audiotran.app

    monkeypatch.setattr(audiotran.app, "main", lambda: 23)
    launcher = Path(__file__).parents[1] / "src" / "audiotran" / "__main__.py"

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(launcher), run_name="__main__")

    assert exc_info.value.code == 23


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


def test_load_settings_resolves_default_and_nested_relative_paths_from_base_dir(
    tmp_path: Path, monkeypatch
):
    from audiotran.app import load_settings

    app_base = tmp_path / "release"
    settings_dir = app_base / "config"
    settings_dir.mkdir(parents=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "ffmpeg": {
                    "ffmpeg_bin": "../tools/ffmpeg/bin/ffmpeg.exe",
                    "ffprobe_bin": "../tools/ffmpeg/bin/ffprobe.exe",
                },
                "recognition": {
                    "model_name": "../models/faster-whisper-small",
                    "device": "cpu",
                },
                "translation": {
                    "provider": "local",
                    "model_path": "../models/translation",
                    "loader_module": "../models/translation/loader.py",
                },
            }
        ),
        encoding="utf-8",
    )
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    monkeypatch.delenv("AUDIOTRAN_SETTINGS", raising=False)
    monkeypatch.setattr("audiotran.app._application_base_dir", lambda: app_base)

    settings = load_settings()

    assert settings["ffmpeg"]["ffmpeg_bin"] == str(
        (app_base / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe").resolve()
    )
    assert settings["ffmpeg"]["ffprobe_bin"] == str(
        (app_base / "tools" / "ffmpeg" / "bin" / "ffprobe.exe").resolve()
    )
    assert settings["recognition"]["model_name"] == str(
        (app_base / "models" / "faster-whisper-small").resolve()
    )
    assert settings["translation"]["model_path"] == str(
        (app_base / "models" / "translation").resolve()
    )
    assert settings["translation"]["loader_module"] == str(
        (app_base / "models" / "translation" / "loader.py").resolve()
    )


def test_load_settings_preserves_named_tools_and_model_aliases(tmp_path: Path):
    from audiotran.app import load_settings

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "ffmpeg": {
                    "ffmpeg_bin": "ffmpeg",
                    "ffprobe_bin": "ffprobe",
                },
                "recognition": {
                    "model_name": "small",
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(settings_path)

    assert settings["ffmpeg"]["ffmpeg_bin"] == "ffmpeg"
    assert settings["ffmpeg"]["ffprobe_bin"] == "ffprobe"
    assert settings["recognition"]["model_name"] == "small"


def test_example_settings_paths_resolve_to_the_documented_release_tree(tmp_path: Path):
    from audiotran.app import load_settings

    release_dir = tmp_path / "audiotran"
    settings_dir = release_dir / "config"
    settings_dir.mkdir(parents=True)
    example_path = Path(__file__).parents[1] / "config" / "example.settings.json"
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")

    settings = load_settings(settings_path)

    assert settings["ffmpeg"]["ffmpeg_bin"] == str(
        (release_dir / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe").resolve()
    )
    assert settings["ffmpeg"]["ffprobe_bin"] == str(
        (release_dir / "tools" / "ffmpeg" / "bin" / "ffprobe.exe").resolve()
    )
    assert settings["recognition"]["model_name"] == str(
        (release_dir / "models" / "faster-whisper-small").resolve()
    )
    assert settings["translation"]["model_path"] == str(
        (release_dir / "models" / "translation").resolve()
    )
    assert settings["translation"]["loader_module"] == str(
        (release_dir / "models" / "translation" / "loader.py").resolve()
    )
