from __future__ import annotations

from pathlib import Path

import pytest

from audiotran.domain.models import Project, SubtitleCue
from audiotran.io.project_store import (
    ProjectFormatError,
    load_project,
    save_project,
)


def test_save_project_and_load_project_round_trip_all_fields(tmp_path: Path):
    project_path = tmp_path / "project.json"
    project = Project(
        audio_path=str(tmp_path / "audio.wav"),
        image_path=str(tmp_path / "cover.png"),
        script_path=str(tmp_path / "script.txt"),
        cues=[
            SubtitleCue(
                id=1,
                start=0.0,
                end=1.25,
                japanese_script="一行目",
                japanese_recognized="いちぎょうめ",
                chinese="第一行",
                confidence=0.98,
                source="script",
                reviewed=True,
            ),
            SubtitleCue(
                id=2,
                start=1.25,
                end=3.5,
                japanese_script="二行目",
                japanese_recognized="にぎょうめ",
                chinese="第二行",
                confidence=None,
                source="asr",
                reviewed=False,
            ),
        ],
        settings={
            "model": "large-v3",
            "beam_size": 5,
            "temperature": 0.2,
            "auto_save": True,
        },
    )

    save_project(project, project_path)
    loaded = load_project(project_path)

    assert loaded == project


def test_load_project_raises_project_format_error_for_malformed_json(tmp_path: Path):
    project_path = tmp_path / "project.json"
    project_path.write_text('{"audio_path": ', encoding="utf-8")

    with pytest.raises(ProjectFormatError) as exc_info:
        load_project(project_path)

    assert exc_info.value.path == project_path


def test_save_project_keeps_original_file_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_path = tmp_path / "project.json"
    project_path.write_text('{"version":"original"}', encoding="utf-8")
    project = Project(
        audio_path="audio.wav",
        image_path="image.png",
        script_path=None,
        cues=[],
        settings={},
    )

    def fail_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("audiotran.io.project_store.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save_project(project, project_path)

    assert project_path.read_text(encoding="utf-8") == '{"version":"original"}'
