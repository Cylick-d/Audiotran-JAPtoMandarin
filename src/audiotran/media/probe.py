from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MediaInfo:
    duration: float
    sample_rate: int | None
    channels: int | None
    format_name: str


class MediaProbeError(ValueError):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"unable to probe media file: {path}")


def probe_media(path: Path, ffprobe_bin: str = "ffprobe") -> MediaInfo:
    path = Path(path)
    command = [
        *shlex.split(ffprobe_bin, posix=False),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise MediaProbeError(path) from None

    try:
        payload = json.loads(completed.stdout)
        return _media_info_from_payload(payload)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise MediaProbeError(path) from None


def _media_info_from_payload(payload: dict[str, Any]) -> MediaInfo:
    format_payload = payload["format"]
    streams_payload = payload["streams"]
    audio_stream = next(
        (stream for stream in streams_payload if stream.get("codec_type") == "audio"),
        {},
    )

    sample_rate = audio_stream.get("sample_rate")
    channels = audio_stream.get("channels")

    return MediaInfo(
        duration=float(format_payload["duration"]),
        sample_rate=int(sample_rate) if sample_rate is not None else None,
        channels=int(channels) if channels is not None else None,
        format_name=str(format_payload["format_name"]),
    )
