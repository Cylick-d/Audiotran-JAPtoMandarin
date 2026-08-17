from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from audiotran.export import export_video
from audiotran.media import SpeechRecognizer, probe_media
from audiotran.pipeline import PipelineFacade
from audiotran.translation import LocalTranslator, OnlineTranslator, TranslationRequest
from audiotran.ui.main_window import MainWindow

DEFAULT_SETTINGS: dict[str, Any] = {
    "ffmpeg": {
        "ffmpeg_bin": "ffmpeg",
        "ffprobe_bin": "ffprobe",
    },
    "recognition": {
        "model_name": "small",
        "device": "auto",
    },
    "translation": {
        "provider": "identity",
        "model_path": "../models/translation",
        "loader_module": "",
        "endpoint": "",
        "api_key": "",
        "timeout": 30.0,
    },
}


def create_application(argv: list[str]) -> QApplication:
    _configure_qt_platform(os.environ)

    application = QApplication.instance()
    if application is None:
        application = QApplication(list(argv))

    if not application.applicationName():
        application.setApplicationName("audiotran")

    return application


class IdentityTranslator:
    def translate(self, request: TranslationRequest) -> list[str]:
        return list(request.texts)


class LazySpeechRecognizer:
    def __init__(self, model_name: str, device: str) -> None:
        self._model_name = model_name
        self._device = device
        self._recognizer: SpeechRecognizer | None = None

    def transcribe(self, path: Path):
        if self._recognizer is None:
            self._recognizer = SpeechRecognizer(self._model_name, device=self._device)
        return self._recognizer.transcribe(path)


def load_settings(settings_path: Path | None = None) -> dict[str, Any]:
    resolved_path = _resolve_settings_path(settings_path)
    settings = _copy_settings(DEFAULT_SETTINGS)
    settings_dir = resolved_path.parent
    if not resolved_path.exists():
        return _resolve_runtime_paths(settings, settings_dir)

    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"settings file must contain a JSON object: {resolved_path}")
    return _resolve_runtime_paths(_merge_settings(settings, payload), settings_dir)


def create_pipeline(settings: dict[str, Any] | None = None) -> PipelineFacade:
    resolved_settings = _copy_settings(DEFAULT_SETTINGS if settings is None else settings)
    ffmpeg_settings = resolved_settings.get("ffmpeg", {})
    recognition_settings = resolved_settings.get("recognition", {})

    recognizer = LazySpeechRecognizer(
        model_name=str(recognition_settings.get("model_name", "small")),
        device=str(recognition_settings.get("device", "auto")),
    )
    translator = _create_translator(resolved_settings.get("translation", {}))

    return PipelineFacade(
        recognizer=recognizer,
        translator=translator,
        exporter=lambda audio, image, subtitle_file, output: export_video(
            audio=audio,
            image=image,
            subtitle_file=subtitle_file,
            output=output,
            ffmpeg_bin=str(ffmpeg_settings.get("ffmpeg_bin", "ffmpeg")),
        ),
        media_probe=lambda path: probe_media(
            path,
            ffprobe_bin=str(ffmpeg_settings.get("ffprobe_bin", "ffprobe")),
        ),
    )


def create_main_window(
    argv: list[str],
    *,
    settings_path: Path | None = None,
    pipeline: PipelineFacade | Any | None = None,
) -> MainWindow:
    create_application(argv)
    resolved_pipeline = pipeline or create_pipeline(load_settings(settings_path))
    return MainWindow(
        project_service=resolved_pipeline,
        recognition_service=resolved_pipeline,
        translation_service=resolved_pipeline,
        export_service=resolved_pipeline,
    )


def main(argv: list[str] | None = None) -> int:
    app_argv = list(sys.argv if argv is None else argv)
    application = create_application(app_argv)
    window = create_main_window(app_argv)
    window.show()
    return application.exec()


def _resolve_settings_path(settings_path: Path | None) -> Path | None:
    base_dir = _application_base_dir()
    if settings_path is not None:
        return _resolve_against_base(Path(settings_path), base_dir)

    env_path = os.environ.get("AUDIOTRAN_SETTINGS")
    if env_path:
        return _resolve_against_base(Path(env_path), base_dir)

    return base_dir / "config" / "settings.json"


def _application_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _configure_qt_platform(environment: dict[str, str]) -> None:
    if "QT_QPA_PLATFORM" in environment:
        return
    if "PYTEST_CURRENT_TEST" in environment:
        environment["QT_QPA_PLATFORM"] = "offscreen"


def _copy_settings(settings: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in settings.items():
        if isinstance(value, dict):
            copied[key] = _copy_settings(value)
        else:
            copied[key] = value
    return copied


def _merge_settings(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_settings(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _resolve_runtime_paths(settings: dict[str, Any], settings_dir: Path) -> dict[str, Any]:
    resolved = _copy_settings(settings)
    ffmpeg = resolved.get("ffmpeg", {})
    recognition = resolved.get("recognition", {})
    translation = resolved.get("translation", {})

    if isinstance(ffmpeg, dict):
        _resolve_setting_in_place(ffmpeg, "ffmpeg_bin", settings_dir, allow_bare_name=True)
        _resolve_setting_in_place(ffmpeg, "ffprobe_bin", settings_dir, allow_bare_name=True)
    if isinstance(recognition, dict):
        _resolve_setting_in_place(recognition, "model_name", settings_dir, allow_bare_name=True)
    if isinstance(translation, dict):
        _resolve_setting_in_place(translation, "model_path", settings_dir, allow_bare_name=False)
        _resolve_setting_in_place(translation, "loader_module", settings_dir, allow_bare_name=False)

    return resolved


def _resolve_setting_in_place(
    mapping: dict[str, Any],
    key: str,
    settings_dir: Path,
    *,
    allow_bare_name: bool,
) -> None:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        return
    if allow_bare_name and _is_bare_name(value):
        return

    mapping[key] = str(_resolve_against_base(Path(value), settings_dir))


def _resolve_against_base(path: Path, base_dir: Path) -> Path:
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def _is_bare_name(value: str) -> bool:
    candidate = Path(value)
    if candidate.is_absolute():
        return False
    if value.startswith("."):
        return False
    return candidate.parent == Path(".")


def _create_translator(settings: dict[str, Any]):
    provider = str(settings.get("provider", "identity")).lower()
    if provider == "identity":
        return IdentityTranslator()
    if provider == "online":
        return OnlineTranslator(
            endpoint=str(settings.get("endpoint", "")),
            api_key=str(settings.get("api_key", "")),
            timeout=float(settings.get("timeout", 30.0)),
        )
    if provider == "local":
        loader_module = str(settings.get("loader_module", "")).strip()
        model_path = Path(str(settings.get("model_path", "models/translation")))
        if loader_module:
            return LocalTranslator(
                model_path,
                model_loader=_load_local_translation_loader(Path(loader_module)),
            )
        return LocalTranslator(model_path)
    raise ValueError(f"unsupported translation provider: {provider}")


def _load_local_translation_loader(loader_path: Path):
    def load_model(model_path: Path):
        spec = importlib.util.spec_from_file_location(
            "audiotran_user_translation_loader",
            loader_path,
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"unable to load translation loader module: {loader_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        factory = getattr(module, "load_model", None)
        if not callable(factory):
            raise ValueError(
                f"translation loader module must define load_model(path): {loader_path}"
            )

        model = factory(model_path)
        if not callable(model):
            raise ValueError(
                f"translation loader must return a callable translator: {loader_path}"
            )
        return model

    return load_model
