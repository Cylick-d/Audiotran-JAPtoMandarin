from __future__ import annotations

from pathlib import Path

import pytest


def test_subtitle_cue_duration_returns_span():
    from audiotran.domain import SubtitleCue

    cue = SubtitleCue(
        id=1,
        start=1.25,
        end=3.75,
        japanese_script="こんにちは",
        japanese_recognized="",
        chinese="",
        confidence=0.95,
        source="script",
        reviewed=False,
    )

    assert cue.duration() == pytest.approx(2.5)


def test_subtitle_cue_validation_reports_negative_time_range():
    from audiotran.domain import SubtitleCue

    cue = SubtitleCue(
        id=2,
        start=4.0,
        end=3.0,
        japanese_script="",
        japanese_recognized="",
        chinese="",
        confidence=None,
        source="asr",
        reviewed=False,
    )

    assert cue.validate() == ["cue 2 has an invalid time range"]


def test_subtitle_cue_validation_reports_out_of_bounds_confidence():
    from audiotran.domain import SubtitleCue

    cue = SubtitleCue(
        id=3,
        start=0.0,
        end=1.0,
        japanese_script="",
        japanese_recognized="",
        chinese="",
        confidence=1.2,
        source="asr",
        reviewed=True,
    )

    assert cue.validate() == ["cue 3 confidence must be between 0 and 1"]


def test_project_validate_skips_filesystem_checks_by_default(tmp_path: Path):
    from audiotran.domain import Project, SubtitleCue

    project = Project(
        audio_path=str(tmp_path / "missing.wav"),
        image_path=str(tmp_path / "missing.png"),
        script_path=None,
        cues=[
            SubtitleCue(
                id=4,
                start=0.0,
                end=1.0,
                japanese_script="",
                japanese_recognized="",
                chinese="",
                confidence=None,
                source="asr",
                reviewed=False,
            )
        ],
        settings={},
    )

    assert project.validate() == []


def test_project_validate_reports_missing_files_when_requested(tmp_path: Path):
    from audiotran.domain import Project, SubtitleCue

    audio_path = tmp_path / "missing.wav"
    image_path = tmp_path / "missing.png"
    project = Project(
        audio_path=str(audio_path),
        image_path=str(image_path),
        script_path=None,
        cues=[
            SubtitleCue(
                id=5,
                start=0.0,
                end=1.0,
                japanese_script="",
                japanese_recognized="",
                chinese="",
                confidence=None,
                source="asr",
                reviewed=False,
            )
        ],
        settings={},
    )

    assert project.validate(check_filesystem=True) == [
        f"audio file does not exist: {audio_path}",
        f"image file does not exist: {image_path}",
    ]
