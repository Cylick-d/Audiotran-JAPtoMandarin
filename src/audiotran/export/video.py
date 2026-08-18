from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable


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
    progress_callback: Callable[[int], None] | None = None,
    total_duration: float | None = None,
) -> ExportResult:
    log_path = output.with_suffix(".log")
    subtitle_paths = [subtitle_file]
    argv = [
        ffmpeg_bin,
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-vf",
        f"scale=1920:-2,{_build_subtitle_filter(subtitle_file)}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        bufsize=1,
    )
    output_lines: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            output_lines.append(line)
            _report_progress_line(line, total_duration, progress_callback)
    process.wait()
    output_log = "".join(output_lines)
    _write_log(log_path, argv, output_log)
    if process.returncode != 0:
        raise ExportError(f"ffmpeg exited with code {process.returncode}")
    if progress_callback is not None:
        progress_callback(100)
    return ExportResult(video_path=output, subtitle_paths=subtitle_paths, log_path=log_path)


def _report_progress_line(
    line: str,
    total_duration: float | None,
    progress_callback: Callable[[int], None] | None,
) -> None:
    if progress_callback is None or not total_duration or total_duration <= 0:
        return

    if not line.startswith("out_time_ms="):
        return
    try:
        elapsed = int(line.partition("=")[2]) / 1_000_000
    except ValueError:
        return
    percent = min(99, max(0, round(elapsed / total_duration * 100)))
    progress_callback(percent)


def _build_subtitle_filter(subtitle_file: Path) -> str:
    normalized = subtitle_file.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")
    return f"subtitles='{normalized}'"


def _write_log(log_path: Path, argv: list[str], output: str) -> None:
    log_path.write_text(
        f"Command: {subprocess.list2cmdline(argv)}\n\n{output}",
        encoding="utf-8",
    )
