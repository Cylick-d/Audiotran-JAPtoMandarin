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
python -m pip install -e .
```

Copy `config/example.settings.json` to `config/settings.json` and update the paths for your machine. You can also point the app at another settings file with `AUDIOTRAN_SETTINGS=C:\path\to\settings.json`.

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

## Packaging

Build the Windows executable with:

```powershell
pyinstaller build/windows.spec
```

PyInstaller includes the PySide6 runtime plus `config/example.settings.json`. Place your real `config/settings.json`, FFmpeg binaries, and any local model files next to the built app before testing on a clean machine.

## Tests

Run the end-to-end pipeline test with:

```powershell
python -m pytest tests/e2e/test_pipeline.py -q
```

Run the full suite with:

```powershell
python -m pytest -q
```
