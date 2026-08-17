# Audio Subtitle Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop application that imports audio, an optional Japanese script, and one cover image; creates editable Japanese/Chinese subtitles through script alignment or local speech recognition; and exports a subtitled MP4 plus subtitle and project files.

**Architecture:** Use a PySide6 desktop shell around small domain modules. Keep project persistence, subtitle segmentation/alignment, translation adapters, media probing, and FFmpeg export independent from the UI so each can be tested without a running window. The UI orchestrates these services through background workers and displays recoverable progress/errors.

**Tech Stack:** Python 3.11+, PySide6, pytest, faster-whisper, FFmpeg/ffprobe, pydantic or dataclasses for domain models, optional HTTP client for user-configured translation APIs, PyInstaller for Windows packaging.

## Global Constraints

- Windows desktop application; first release targets WAV, MP3, M4A audio and JPG, PNG, WEBP cover images.
- Local speech recognition is the default.
- Online translation is opt-in; audio is never uploaded by the application.
- The first release uses one cover image for the full duration and exports MP4, SRT, ASS, JSON, and a log.
- Keep script text, recognized text, and translated text as separate fields.
- Do not implement platform upload, moderation evasion, content hiding, or safety bypass features.
- Preserve generated intermediates after recoverable failures so the user can resume.

---

### Task 1: Bootstrap the Python application and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/audiotran/__init__.py`
- Create: `src/audiotran/__main__.py`
- Create: `src/audiotran/app.py`
- Create: `tests/test_bootstrap.py`
- Create: `README.md`

**Interfaces:**
- Produces an importable `audiotran` package and a `python -m audiotran` entry point.
- `audiotran.app.create_application(argv: list[str]) -> QApplication` creates the Qt application without starting the event loop.

- [ ] **Step 1: Write the failing smoke test**

```python
def test_package_imports():
    import audiotran
    assert audiotran.__version__
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_bootstrap.py -q`
Expected: FAIL because the package does not exist.

- [ ] **Step 3: Add the package metadata and minimal entry point**

Define the project metadata and dependencies in `pyproject.toml`, expose a non-empty `__version__`, and make `__main__.py` call a small `main()` function that creates the application and exits cleanly when no window is shown.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_bootstrap.py -q`
Expected: PASS.

- [ ] **Step 5: Add setup documentation**

Document the Python version, FFmpeg requirement, virtual environment setup, and test command in `README.md`.

- [ ] **Step 6: Commit the bootstrap**

Run: `git add pyproject.toml src tests README.md && git commit -m "chore: bootstrap audiotran desktop app"`

### Task 2: Define project and subtitle domain models

**Files:**
- Create: `src/audiotran/domain/models.py`
- Create: `src/audiotran/domain/__init__.py`
- Create: `tests/domain/test_models.py`

**Interfaces:**
- `SubtitleCue(id: int, start: float, end: float, japanese_script: str, japanese_recognized: str, chinese: str, confidence: float | None, source: Literal["script", "asr"], reviewed: bool)`.
- `Project(audio_path: str, image_path: str, script_path: str | None, cues: list[SubtitleCue], settings: dict[str, object])`.
- `SubtitleCue.duration() -> float` and `Project.validate() -> list[str]`.

- [ ] **Step 1: Write tests for duration and validation**

Test that a valid cue returns `end - start`, negative time ranges are reported, confidence outside `0..1` is reported, and a project requires an existing audio/image path only when validation is asked against the filesystem.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/domain/test_models.py -q`
Expected: FAIL because the model classes are missing.

- [ ] **Step 3: Implement dataclasses and validation**

Use dataclasses and typed literals. Keep validation deterministic and free of Qt or FFmpeg dependencies.

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest tests/domain/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add src/audiotran/domain tests/domain && git commit -m "feat: add project and subtitle models"`

### Task 3: Implement project JSON persistence and encoding detection

**Files:**
- Create: `src/audiotran/io/project_store.py`
- Create: `src/audiotran/io/script_reader.py`
- Create: `tests/io/test_project_store.py`
- Create: `tests/io/test_script_reader.py`

**Interfaces:**
- `read_script(path: Path) -> str` tries UTF-8, Shift-JIS, and UTF-16 in that order and raises `ScriptEncodingError` with the path when all fail.
- `save_project(project: Project, path: Path) -> None` writes UTF-8 JSON atomically through a temporary file in the destination directory.
- `load_project(path: Path) -> Project` reconstructs the domain model and rejects malformed JSON with `ProjectFormatError`.

- [ ] **Step 1: Write tests for all supported encodings and round-trip persistence**

Create temporary files encoded as UTF-8, Shift-JIS, and UTF-16; assert the same Japanese text is returned. Build a project with two cues, save it, load it, and assert all fields and settings match.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest tests/io -q`
Expected: FAIL because the reader and store do not exist.

- [ ] **Step 3: Implement the reader and store**

Use `Path.read_bytes()` and explicit decoders. Serialize enums as strings and preserve all three text fields. Use `os.replace()` for the final atomic move.

- [ ] **Step 4: Test malformed files and safe recovery**

Add a test that malformed JSON raises `ProjectFormatError` and does not overwrite the original project file.

- [ ] **Step 5: Run all IO tests**

Run: `python -m pytest tests/io -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Run: `git add src/audiotran/io tests/io && git commit -m "feat: persist projects and read Japanese scripts"`

### Task 4: Add subtitle segmentation and script/ASR alignment

**Files:**
- Create: `src/audiotran/subtitles/segmenter.py`
- Create: `src/audiotran/subtitles/alignment.py`
- Create: `src/audiotran/subtitles/__init__.py`
- Create: `tests/subtitles/test_segmenter.py`
- Create: `tests/subtitles/test_alignment.py`

**Interfaces:**
- `segment_text(text: str, max_chars: int = 22) -> list[str]` splits on Japanese punctuation and hard limits without returning empty segments.
- `align_script(script_segments: list[str], recognized_segments: list[SubtitleCue]) -> list[SubtitleCue]` copies matched script text into `japanese_script`, preserves recognized text, sets `source="script"`, and assigns a confidence score.
- `split_long_cue(cue: SubtitleCue, max_chars: int = 22) -> list[SubtitleCue]` divides a cue proportionally by text length while preserving its full time span.

- [ ] **Step 1: Write segmentation tests**

Cover punctuation boundaries, long text, empty lines, and the guarantee that all non-whitespace source text appears once in the output after normalization.

- [ ] **Step 2: Run segmentation tests and verify failure**

Run: `python -m pytest tests/subtitles/test_segmenter.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement segmentation**

Prefer `。！？` and newline boundaries, then split overlong segments at `、` or whitespace-equivalent boundaries, and only use a hard character split as a last resort.

- [ ] **Step 4: Write alignment tests**

Test exact matches, small suffix differences, unmatched script segments, low-confidence matching, and preservation of recognized text.

- [ ] **Step 5: Implement alignment and splitting**

Normalize punctuation and whitespace for comparison, use a standard-library similarity metric, and mark unmatched or weak matches rather than silently discarding them.

- [ ] **Step 6: Run subtitle tests**

Run: `python -m pytest tests/subtitles -q`
Expected: PASS.

- [ ] **Step 7: Commit**

Run: `git add src/audiotran/subtitles tests/subtitles && git commit -m "feat: segment and align subtitle cues"`

### Task 5: Add media probing and local speech-recognition service

**Files:**
- Create: `src/audiotran/media/probe.py`
- Create: `src/audiotran/media/asr.py`
- Create: `src/audiotran/media/__init__.py`
- Create: `tests/media/test_probe.py`
- Create: `tests/media/test_asr.py`

**Interfaces:**
- `MediaInfo(duration: float, sample_rate: int | None, channels: int | None, format_name: str)`.
- `probe_media(path: Path, ffprobe_bin: str = "ffprobe") -> MediaInfo`.
- `SpeechRecognizer(model_name: str, device: str = "auto")` with `transcribe(path: Path) -> list[SubtitleCue]`.

- [ ] **Step 1: Write probe tests with a fake ffprobe executable**

Feed deterministic JSON output and assert parsing. Test nonzero process exit raises `MediaProbeError` containing the input path.

- [ ] **Step 2: Run probe tests and verify failure**

Run: `python -m pytest tests/media/test_probe.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement probe parsing**

Call ffprobe with JSON output, parse duration and stream metadata, and keep subprocess calls isolated behind the probe function.

- [ ] **Step 4: Write ASR tests using an injected fake transcriber**

Test conversion of model segments into `SubtitleCue` objects, source `"asr"`, preserved timestamps, and a clean error when the model is missing. Do not download a model in unit tests.

- [ ] **Step 5: Implement the recognizer adapter**

Import faster-whisper lazily, expose model/device settings, and map model output to the domain model. Keep model loading outside the UI thread.

- [ ] **Step 6: Run media tests**

Run: `python -m pytest tests/media -q`
Expected: PASS.

- [ ] **Step 7: Commit**

Run: `git add src/audiotran/media tests/media && git commit -m "feat: probe media and transcribe locally"`

### Task 6: Add translation adapters and translation settings

**Files:**
- Create: `src/audiotran/translation/base.py`
- Create: `src/audiotran/translation/local.py`
- Create: `src/audiotran/translation/online.py`
- Create: `src/audiotran/translation/__init__.py`
- Create: `tests/translation/test_adapters.py`

**Interfaces:**
- `TranslationRequest(texts: list[str], glossary: dict[str, str])`.
- `Translator.translate(request: TranslationRequest) -> list[str]`.
- `LocalTranslator(model_path: Path)` and `OnlineTranslator(endpoint: str, api_key: str, timeout: float = 30.0)`.

- [ ] **Step 1: Write adapter contract tests**

Use a fake translator to assert ordering, one output per input, glossary forwarding, and that an adapter error leaves the original Japanese cues unchanged.

- [ ] **Step 2: Run translation tests and verify failure**

Run: `python -m pytest tests/translation -q`
Expected: FAIL.

- [ ] **Step 3: Implement the base contract and local adapter boundary**

Keep local model loading lazy and make the actual model callable injectable for tests. Do not hard-code a vendor or model URL.

- [ ] **Step 4: Implement the opt-in online adapter**

Send only the requested text payload, enforce a timeout, redact API keys from errors, and raise `TranslationError` without deleting prior outputs.

- [ ] **Step 5: Run translation tests**

Run: `python -m pytest tests/translation -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Run: `git add src/audiotran/translation tests/translation && git commit -m "feat: support local and opt-in online translation"`

### Task 7: Implement SRT/ASS subtitle rendering and FFmpeg export

**Files:**
- Create: `src/audiotran/export/subtitles.py`
- Create: `src/audiotran/export/video.py`
- Create: `src/audiotran/export/__init__.py`
- Create: `tests/export/test_subtitles.py`
- Create: `tests/export/test_video.py`

**Interfaces:**
- `render_srt(cues: list[SubtitleCue], mode: Literal["zh", "bilingual"]) -> str`.
- `render_ass(cues: list[SubtitleCue], mode: Literal["zh", "bilingual"], style: SubtitleStyle) -> str`.
- `export_video(audio: Path, image: Path, subtitle_file: Path, output: Path, ffmpeg_bin: str = "ffmpeg") -> ExportResult`.
- `ExportResult(video_path: Path, subtitle_paths: list[Path], log_path: Path)`.

- [ ] **Step 1: Write SRT/ASS golden tests**

Use two cues with known times and text. Assert SRT timestamp formatting, Chinese-only output, bilingual two-line output, ASS style fields, and escaping of ASS special characters.

- [ ] **Step 2: Run subtitle export tests and verify failure**

Run: `python -m pytest tests/export/test_subtitles.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement deterministic subtitle renderers**

Format timestamps with millisecond precision, use the selected display mode, and keep rendering independent of FFmpeg.

- [ ] **Step 4: Write video export tests with a fake ffmpeg executable**

Assert the command includes looped image input, audio input, subtitle filter, H.264 video, AAC audio, shortest output, and the requested output path. Assert failed processes raise `ExportError` and write a log.

- [ ] **Step 5: Implement the exporter**

Use an argument list rather than a shell command string. Write the command and combined process output to the project log. Do not delete intermediate subtitle files when export fails.

- [ ] **Step 6: Run export tests**

Run: `python -m pytest tests/export -q`
Expected: PASS.

- [ ] **Step 7: Commit**

Run: `git add src/audiotran/export tests/export && git commit -m "feat: render subtitles and export MP4 video"`

### Task 8: Build the PySide6 project workflow UI

**Files:**
- Create: `src/audiotran/ui/main_window.py`
- Create: `src/audiotran/ui/widgets.py`
- Create: `src/audiotran/ui/workers.py`
- Create: `src/audiotran/ui/__init__.py`
- Create: `tests/ui/test_main_window.py`

**Interfaces:**
- `MainWindow(project_service, recognition_service, translation_service, export_service)`.
- `ProjectWorker.run() -> WorkerResult` emits progress, result, and error signals.

- [ ] **Step 1: Write UI smoke tests**

Use a Qt test fixture to instantiate the window, assert the three-pane layout exists, and assert the import controls and Chinese/bilingual mode controls are present.

- [ ] **Step 2: Run the UI test and verify failure**

Run: `python -m pytest tests/ui/test_main_window.py -q`
Expected: FAIL because the UI modules do not exist.

- [ ] **Step 3: Implement the static window shell**

Create left project panel, center subtitle table, and right preview/export panel. Keep all long-running work outside the UI thread.

- [ ] **Step 4: Add import and project actions**

Wire audio, image, script, open, save, and new-project actions to the persistence and input services. Validate extensions before starting processing.

- [ ] **Step 5: Add processing workers and progress states**

Add separate actions for script alignment and ASR, then translation and export. Display recoverable errors and retain the last successful stage.

- [ ] **Step 6: Add subtitle editing and preview**

Bind table edits to `SubtitleCue` objects, provide split/merge and play-current-cue actions, and update the preview for Chinese-only or bilingual display.

- [ ] **Step 7: Run UI tests and the full suite**

Run: `python -m pytest tests/ui/test_main_window.py -q` and then `python -m pytest -q`.
Expected: PASS.

- [ ] **Step 8: Commit**

Run: `git add src/audiotran/ui tests/ui && git commit -m "feat: add desktop project workflow"`

### Task 9: Add packaging, sample configuration, and end-to-end verification

**Files:**
- Create: `build/windows.spec`
- Create: `config/example.settings.json`
- Create: `tests/e2e/test_pipeline.py`
- Modify: `README.md`

**Interfaces:**
- The end-to-end test uses fake recognizer, translator, ffprobe, and ffmpeg services so it runs without model downloads or network access.

- [ ] **Step 1: Write the end-to-end test**

Create a temporary project with a fake audio path, image path, script, two recognized segments, translated output, and a fake export. Assert the project JSON, SRT, ASS, and final MP4 placeholder are produced and reopening the project preserves the cues.

- [ ] **Step 2: Run the end-to-end test and verify failure**

Run: `python -m pytest tests/e2e/test_pipeline.py -q`
Expected: FAIL until the service orchestration is connected.

- [ ] **Step 3: Implement the pipeline facade**

Add a small application service that chooses script alignment when a script is present, otherwise ASR, then translates and exports using injected collaborators.

- [ ] **Step 4: Run all automated tests**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Add Windows packaging configuration**

Configure PyInstaller to include the PySide6 entry point and runtime assets. Document where the user places FFmpeg and local model files.

- [ ] **Step 6: Perform manual verification with the sample files**

Run the packaged or development application with `C:\Users\Xingzhi\Downloads\シコらせ西原さん\台本\4.間.txt` and `C:\Users\Xingzhi\Downloads\シコらせ西原さん\本編\SEあり\4.間.wav`, a user-selected cover image, and a local-only translation configuration. Verify that the preview plays, the subtitle table is editable, both display modes export, and a failed export leaves the project and subtitle files intact.

- [ ] **Step 7: Commit the release setup**

Run: `git add build config tests/e2e README.md && git commit -m "chore: package and verify Windows release"`

