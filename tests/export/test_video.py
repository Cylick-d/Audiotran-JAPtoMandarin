from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _write_fake_ffmpeg(tmp_path: Path) -> Path:
    script_path = tmp_path / "fake_ffmpeg.py"
    wrapper_path = tmp_path / "fake_ffmpeg.cmd"

    script_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "Path(os.environ['FAKE_FFMPEG_ARGS_LOG']).write_text('|'.join(sys.argv[1:]), encoding='utf-8')",
                "print('fake ffmpeg stdout')",
                "print('fake ffmpeg stderr', file=sys.stderr)",
                "exit_code = int(os.environ.get('FAKE_FFMPEG_EXIT_CODE', '0'))",
                "if exit_code == 0:",
                "    Path(sys.argv[-1]).write_text('video', encoding='utf-8')",
                "raise SystemExit(exit_code)",
            ]
        ),
        encoding="utf-8",
    )
    wrapper_path.write_text(
        f'@echo off\r\n"{sys.executable}" "%~dp0fake_ffmpeg.py" %*\r\n',
        encoding="utf-8",
    )
    return wrapper_path


def test_export_video_invokes_ffmpeg_with_expected_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from audiotran.export.video import export_video

    ffmpeg_bin = _write_fake_ffmpeg(tmp_path)
    args_log = tmp_path / "args.log"
    monkeypatch.setenv("FAKE_FFMPEG_ARGS_LOG", str(args_log))

    audio = tmp_path / "audio.wav"
    image = tmp_path / "cover.png"
    subtitle = tmp_path / "captions.ass"
    output = tmp_path / "out.mp4"

    audio.write_text("audio", encoding="utf-8")
    image.write_text("image", encoding="utf-8")
    subtitle.write_text("subs", encoding="utf-8")

    result = export_video(audio=audio, image=image, subtitle_file=subtitle, output=output, ffmpeg_bin=str(ffmpeg_bin))

    assert result.video_path == output
    assert result.subtitle_paths == [subtitle]
    assert result.log_path == output.with_suffix(".log")
    assert output.exists()

    args = args_log.read_text(encoding="utf-8")
    assert "-loop|1" in args
    assert f"-i|{image}" in args
    assert f"-i|{audio}" in args
    assert "-vf|" in args
    assert "subtitles='" in args
    assert "|-c:v|libx264|" in args
    assert "-c:a|aac" in args
    assert "-shortest" in args
    assert args.endswith(f"|{output}")


def test_build_subtitle_filter_escapes_windows_drive_colon_and_apostrophe():
    from audiotran.export.video import _build_subtitle_filter

    subtitle = Path(r"C:\Media\it's.ass")

    assert _build_subtitle_filter(subtitle) == "subtitles='C\\:/Media/it\\'s.ass'"


def test_export_video_raises_and_writes_log_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from audiotran.export.video import ExportError, export_video

    ffmpeg_bin = _write_fake_ffmpeg(tmp_path)
    args_log = tmp_path / "args.log"
    monkeypatch.setenv("FAKE_FFMPEG_ARGS_LOG", str(args_log))
    monkeypatch.setenv("FAKE_FFMPEG_EXIT_CODE", "7")

    audio = tmp_path / "audio.wav"
    image = tmp_path / "cover.png"
    subtitle = tmp_path / "captions.ass"
    output = tmp_path / "out.mp4"

    audio.write_text("audio", encoding="utf-8")
    image.write_text("image", encoding="utf-8")
    subtitle.write_text("subs", encoding="utf-8")

    with pytest.raises(ExportError):
        export_video(audio=audio, image=image, subtitle_file=subtitle, output=output, ffmpeg_bin=str(ffmpeg_bin))

    log_path = output.with_suffix(".log")
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "Command:" in log_text
    assert "fake ffmpeg stdout" in log_text
    assert "fake ffmpeg stderr" in log_text
    assert str(output) in log_text
    assert subtitle.exists()
