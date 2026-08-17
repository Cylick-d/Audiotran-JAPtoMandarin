from __future__ import annotations

from pathlib import Path

import pytest


def test_probe_media_parses_ffprobe_json_from_fake_executable(tmp_path: Path):
    from audiotran.media import MediaInfo, probe_media

    ffprobe_path = tmp_path / "fake_ffprobe.py"
    ffprobe_path.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                '  "format": {"duration": "12.5", "format_name": "wav"},',
                '  "streams": [',
                '    {"codec_type": "audio", "sample_rate": "48000", "channels": 2}',
                "  ]",
                "}))",
            ]
        ),
        encoding="utf-8",
    )
    media_path = tmp_path / "clip.wav"
    media_path.write_bytes(b"placeholder")

    info = probe_media(media_path, ffprobe_bin=f"python {ffprobe_path}")

    assert info == MediaInfo(
        duration=12.5,
        sample_rate=48000,
        channels=2,
        format_name="wav",
    )


def test_probe_media_raises_media_probe_error_when_ffprobe_fails(tmp_path: Path):
    from audiotran.media import MediaProbeError, probe_media

    ffprobe_path = tmp_path / "fake_ffprobe_fail.py"
    ffprobe_path.write_text("raise SystemExit(2)\n", encoding="utf-8")
    media_path = tmp_path / "broken.wav"
    media_path.write_bytes(b"placeholder")

    with pytest.raises(MediaProbeError) as exc_info:
        probe_media(media_path, ffprobe_bin=f"python {ffprobe_path}")

    assert str(media_path) in str(exc_info.value)
    assert exc_info.value.path == media_path
