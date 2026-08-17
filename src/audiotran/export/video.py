from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(slots=True, frozen=True)
class ExportResult:
    video_path: Path
    subtitle_paths: list[Path]
    log_path: Path


class ExportError(RuntimeError):
    pass


def export_video(
    audio: Path,
    image: Path,
    subtitle_file: Path,
    output: Path,
    ffmpeg_bin: str = "ffmpeg",
) -> ExportResult:
    log_path = output.with_suffix(".log")
    subtitle_paths = [subtitle_file]
    argv = [
        ffmpeg_bin,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-vf",
        _build_subtitle_filter(subtitle_file),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    completed = subprocess.run(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        shell=False,
        check=False,
    )
    _write_log(log_path, argv, completed.stdout or "")
    if completed.returncode != 0:
        raise ExportError(f"ffmpeg exited with code {completed.returncode}")
    return ExportResult(video_path=output, subtitle_paths=subtitle_paths, log_path=log_path)


def _build_subtitle_filter(subtitle_file: Path) -> str:
    normalized = subtitle_file.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")
    return f"subtitles='{normalized}'"


def _write_log(log_path: Path, argv: list[str], output: str) -> None:
    log_path.write_text(
        f"Command: {subprocess.list2cmdline(argv)}\n\n{output}",
        encoding="utf-8",
    )
