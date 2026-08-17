from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_probe_media_passes_spaced_executable_path_as_single_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from audiotran.media import MediaInfo, probe_media

    ffprobe_path = tmp_path / "fake ffprobe.exe"
    media_path = tmp_path / "clip.wav"
    media_path.write_bytes(b"placeholder")
    seen_command: list[str] | None = None

    def fake_run(command: list[str], **_kwargs):
        nonlocal seen_command
        seen_command = command
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '{"format":{"duration":"12.5","format_name":"wav"},'
                '"streams":[{"codec_type":"audio","sample_rate":"48000","channels":2}]}'
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    info = probe_media(media_path, ffprobe_bin=str(ffprobe_path))

    assert info == MediaInfo(
        duration=12.5,
        sample_rate=48000,
        channels=2,
        format_name="wav",
    )
    assert seen_command == [
        str(ffprobe_path),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(media_path),
    ]


def test_probe_media_raises_media_probe_error_when_ffprobe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from audiotran.media import MediaProbeError, probe_media

    ffprobe_path = tmp_path / "fake ffprobe.exe"
    media_path = tmp_path / "broken.wav"
    media_path.write_bytes(b"placeholder")

    def fake_run(command: list[str], **_kwargs):
        raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MediaProbeError) as exc_info:
        probe_media(media_path, ffprobe_bin=str(ffprobe_path))

    assert str(media_path) in str(exc_info.value)
    assert exc_info.value.path == media_path
