from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from audiotran.domain.models import Project, SubtitleCue


class ProjectFormatError(ValueError):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"project file has an invalid format: {path}")


def save_project(project: Project, path: Path) -> None:
    path = Path(path)
    payload = _project_to_payload(project)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def load_project(path: Path) -> Project:
    path = Path(path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _project_from_payload(payload, path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise ProjectFormatError(path) from None


def _project_to_payload(project: Project) -> dict[str, Any]:
    return {
        "audio_path": project.audio_path,
        "image_path": project.image_path,
        "script_path": project.script_path,
        "cues": [_cue_to_payload(cue) for cue in project.cues],
        "settings": project.settings,
    }


def _cue_to_payload(cue: SubtitleCue) -> dict[str, Any]:
    return asdict(cue)


def _project_from_payload(payload: Any, path: Path) -> Project:
    if not isinstance(payload, dict):
        raise ProjectFormatError(path)

    audio_path = _require_type(payload, "audio_path", str)
    image_path = _require_type(payload, "image_path", str)
    script_path = payload.get("script_path")
    if script_path is not None and not isinstance(script_path, str):
        raise ProjectFormatError(path)

    cues_payload = _require_type(payload, "cues", list)
    settings = _require_type(payload, "settings", dict)

    return Project(
        audio_path=audio_path,
        image_path=image_path,
        script_path=script_path,
        cues=[_cue_from_payload(cue_payload, path) for cue_payload in cues_payload],
        settings=settings,
    )


def _cue_from_payload(payload: Any, path: Path) -> SubtitleCue:
    if not isinstance(payload, dict):
        raise ProjectFormatError(path)

    source = _require_type(payload, "source", str)
    if source not in {"script", "asr"}:
        raise ProjectFormatError(path)

    confidence = payload.get("confidence")
    if confidence is not None and not isinstance(confidence, (float, int)):
        raise ProjectFormatError(path)

    reviewed = payload.get("reviewed")
    if not isinstance(reviewed, bool):
        raise ProjectFormatError(path)

    return SubtitleCue(
        id=_require_type(payload, "id", int),
        start=float(_require_type(payload, "start", (float, int))),
        end=float(_require_type(payload, "end", (float, int))),
        japanese_script=_require_type(payload, "japanese_script", str),
        japanese_recognized=_require_type(payload, "japanese_recognized", str),
        chinese=_require_type(payload, "chinese", str),
        confidence=None if confidence is None else float(confidence),
        source=source,
        reviewed=reviewed,
    )


def _require_type(payload: dict[str, Any], key: str, expected_type: type[Any] | tuple[type[Any], ...]) -> Any:
    value = payload[key]
    if isinstance(expected_type, tuple):
        valid = isinstance(value, expected_type)
    else:
        valid = isinstance(value, expected_type)

    if not valid:
        raise TypeError(f"{key} has an invalid type")

    return value
