# AudioTran

## Requirements

- Python 3.11 or newer
- Windows 10 or Windows 11
- FFmpeg and ffprobe available either on `PATH` or through `config/settings.json`
- A local Faster Whisper model directory if you want to avoid first-run model downloads

## Setup

Create and activate a virtual environment, then install the project in editable mode:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[build]"
```

Copy `config/example.settings.json` to `config/settings.json` and update the paths for your machine. You can also point the app at another settings file with `AUDIOTRAN_SETTINGS=C:\path\to\settings.json`.

`config/settings.json` is resolved relative to the executable or project base, not the shell working directory. Any relative `ffmpeg`, `ffprobe`, local model, or local translation loader paths inside that settings file are resolved relative to the settings file's own directory. Absolute paths are preserved, and bare names like `ffmpeg` or `small` keep their normal PATH or model-alias behavior.

## Windows Runtime Layout

The current app reads these paths from `config/settings.json`:

- `ffmpeg.ffmpeg_bin`: path to `ffmpeg.exe`
- `ffmpeg.ffprobe_bin`: path to `ffprobe.exe`
- `recognition.model_name`: either a named Faster Whisper model or a local model directory
- `translation.provider`: `identity`, `local`, or `online`

For an offline Windows setup, keep the release tree like this:

```text
audiotran/
  audiotran.exe
  config/
    settings.json
  tools/
    ffmpeg/
      bin/
        ffmpeg.exe
        ffprobe.exe
  models/
    faster-whisper-small/
    translation/
      loader.py
      ...
```

`identity` keeps translation local-only by copying the Japanese source text into the translated field. `local` expects a Python loader module at `translation.loader_module` that defines `load_model(path)` and returns a callable that accepts `(texts, glossary)` and returns one translated string per input. `online` is opt-in and only sends subtitle text, never audio.

## Launch

Run the development build with:

```powershell
python -m audiotran
```

The application now opens the PySide6 workspace window directly. Import audio, an image, and an optional script; use `Run ASR`, `Align Script`, `Translate`, and `Export` to drive the first-release workflow.

## Project Files

Saved project JSON includes `schema_version: 1`. Unversioned projects from the initial release are migrated on load with defaults for missing optional script, cue text, confidence, source, review, and settings fields. Files from newer schema versions or files with unknown project/cue fields are rejected rather than silently discarding data.

## Packaging

Build the Windows executable with:

```powershell
pyinstaller build/windows.spec
```

The `build` extra installs `PyInstaller 6.x`, which matches the `PyInstaller.utils.hooks` imports used by `build/windows.spec`. PyInstaller includes the PySide6 runtime plus `config/example.settings.json`. Place your real `config/settings.json`, FFmpeg binaries, and any local model files next to the built app before testing on a clean machine.

## Tests

Run the end-to-end pipeline test with:

```powershell
python -m pytest tests/e2e/test_pipeline.py -q
```

Run the full suite with:

```powershell
python -m pytest -q
```
