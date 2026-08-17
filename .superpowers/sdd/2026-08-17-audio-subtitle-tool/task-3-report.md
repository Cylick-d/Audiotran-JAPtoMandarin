# Task 3 Report

Date: 2026-08-17

## Scope

Implemented project JSON persistence and Japanese script encoding detection for the Audio Subtitle Tool task brief.

## Changed files

- `src/audiotran/io/__init__.py`
- `src/audiotran/io/project_store.py`
- `src/audiotran/io/script_reader.py`
- `tests/io/test_project_store.py`
- `tests/io/test_script_reader.py`

## Summary of work

- Added `read_script(path: Path) -> str` with UTF-8, Shift-JIS, and UTF-16 decode attempts in order.
- Added `ScriptEncodingError` carrying the failing path.
- Added `save_project(project: Project, path: Path) -> None` using a UTF-8 JSON temp file in the destination directory followed by `os.replace(...)`.
- Added `load_project(path: Path) -> Project` with strict reconstruction of `Project` and `SubtitleCue`.
- Added `ProjectFormatError` carrying the failing path.
- Added IO tests for supported script encodings, unsupported encoding failure, project save/load round-trip, malformed JSON rejection, and atomic-write protection when replace fails.

## Commands and outputs

### 1. Read the task brief

Command:

```powershell
Get-Content D:\audiotran\.superpowers\sdd\2026-08-17-audio-subtitle-tool\task-3-brief.md
```

Output:

```text
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
```

### 2. Red phase: verify failing IO tests

Command:

```powershell
python -m pytest tests/io -q
```

Output:

```text
=================================== ERRORS ====================================
_______________ ERROR collecting tests/io/test_project_store.py _______________
ImportError while importing test module 'D:\audiotran\tests\io\test_project_store.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\io\test_project_store.py:8: in <module>
    from audiotran.io.project_store import (
E   ModuleNotFoundError: No module named 'audiotran.io'
_______________ ERROR collecting tests/io/test_script_reader.py _______________
ImportError while importing test module 'D:\audiotran\tests\io\test_script_reader.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
D:\anaconda\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\io\test_script_reader.py:7: in <module>
    from audiotran.io.script_reader import ScriptEncodingError, read_script
E   ModuleNotFoundError: No module named 'audiotran.io'
=========================== short test summary info ============================
ERROR tests/io/test_project_store.py
ERROR tests/io/test_script_reader.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.35s
```

### 3. Green phase: verify IO tests pass after implementation

Command:

```powershell
python -m pytest tests/io -q
```

Output:

```text
.......                                                                  [100%]
7 passed in 0.16s
```

### 4. Commit the scoped Task 3 changes

Command:

```powershell
git add src/audiotran/io tests/io && git commit -m "feat: persist projects and read Japanese scripts"
```

Output:

```text
warning: in the working copy of 'src/audiotran/io/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/audiotran/io/project_store.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/audiotran/io/script_reader.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/io/test_project_store.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/io/test_script_reader.py', LF will be replaced by CRLF the next time Git touches it
[main 3930f15] feat: persist projects and read Japanese scripts
 5 files changed, 283 insertions(+)
 create mode 100644 src/audiotran/io/__init__.py
 create mode 100644 src/audiotran/io/project_store.py
 create mode 100644 src/audiotran/io/script_reader.py
 create mode 100644 tests/io/test_project_store.py
 create mode 100644 tests/io/test_script_reader.py
```

### 5. Fresh verification after commit

Commands:

```powershell
python -m pytest tests/io -q
git rev-parse HEAD
git show --stat --oneline --no-patch HEAD
git status --short
```

Outputs:

```text
.......                                                                  [100%]
7 passed in 0.11s
```

```text
3930f153bd4ecbc3240730725767aefe6ddeb57d
```

```text
3930f15 feat: persist projects and read Japanese scripts
```

```text
?? "\343\202\267\343\202\263\343\202\211\343\201\233\350\245\277\345\216\237\343\201\225\343\202\223/"
```

## Commit

- Short hash: `3930f15`
- Full hash: `3930f153bd4ecbc3240730725767aefe6ddeb57d`
- Message: `feat: persist projects and read Japanese scripts`

## Concerns

- The repository still has one unrelated untracked directory after this task. I did not stage or modify it.
- Git emitted line-ending warnings during commit (`LF` to `CRLF` on next touch). The commit succeeded and tests remained green, but the repository may want an explicit line-ending policy later.

## Fix Round 1

Date: 2026-08-17

### Scope

Addressed reviewer findings for Task 3:

- `read_script()` now decodes UTF-8 BOM safely while preserving the intended fallback order.
- `save_project()` now registers the temp path before writing so failures during serialization, flush, or fsync still clean up the temp file.
- `load_project()` now rejects boolean values for numeric cue fields while keeping `ProjectFormatError` behavior.

### Commands and outputs

#### 1. Red phase: verify reviewer regression tests fail before the fix

Command:

```powershell
python -m pytest tests/io/test_script_reader.py -q
```

Output:

```text
...F.                                                                    [100%]
================================== FAILURES ===================================
______________________ test_read_script_strips_utf8_bom _______________________

tmp_path = WindowsPath('C:/Users/Xingzhi/AppData/Local/Temp/pytest-of-Xingzhi/pytest-34/test_read_script_strips_utf8_b0')

    def test_read_script_strips_utf8_bom(tmp_path: Path):
        script_path = tmp_path / "script-utf8-bom.txt"
        expected = "字幕テスト\nこんにちは世界"
        script_path.write_bytes(expected.encode("utf-8-sig"))

>       assert read_script(script_path) == expected
E       AssertionError: assert '\ufeff字幕テスト\nこんにちは世界' == '字幕テスト\nこんにちは世界'
E
E         - 字幕テスト
E         + \ufeff字幕テスト
E         ? +
E           こんにちは世界

tests\io\test_script_reader.py:26: AssertionError
=========================== short test summary info ============================
FAILED tests/io/test_script_reader.py::test_read_script_strips_utf8_bom - AssertionError
1 failed, 4 passed in 0.29s
```

Command:

```powershell
python -m pytest tests/io/test_project_store.py -q
```

Output:

```text
...FFFFF                                                                 [100%]
================================== FAILURES ===================================
________ test_save_project_removes_temp_file_when_serialization_fails _________

tmp_path = WindowsPath('C:/Users/Xingzhi/AppData/Local/Temp/pytest-of-Xingzhi/pytest-33/test_save_project_removes_temp0')

    def test_save_project_removes_temp_file_when_serialization_fails(tmp_path: Path):
        project_path = tmp_path / "project.json"
        project = Project(
            audio_path="audio.wav",
            image_path="image.png",
            script_path=None,
            cues=[],
            settings={"bad": {1, 2, 3}},
        )

        with pytest.raises(TypeError):
            save_project(project, project_path)

>       assert list(tmp_path.glob("project.json.*.tmp")) == []
E       AssertionError: assert [WindowsPath('C:/Users/Xingzhi/AppData/Local/Temp/pytest-of-Xingzhi/pytest-33/test_save_project_removes_temp0/project.json.vqiu_b32.tmp')] == []
E         Left contains one more item: WindowsPath('C:/Users/Xingzhi/AppData/Local/Temp/pytest-of-Xingzhi/pytest-33/test_save_project_removes_temp0/project.json.vqiu_b32.tmp')
E         Use -v to get more diff

tests\io\test_project_store.py:106: AssertionError
_______ test_load_project_rejects_bool_for_numeric_cue_fields[id-True] ________
_____ test_load_project_rejects_bool_for_numeric_cue_fields[start-False] ______
_______ test_load_project_rejects_bool_for_numeric_cue_fields[end-True] _______
___ test_load_project_rejects_bool_for_numeric_cue_fields[confidence-False] ___

E       Failed: DID NOT RAISE <class 'audiotran.io.project_store.ProjectFormatError'>

=========================== short test summary info ============================
FAILED tests/io/test_project_store.py::test_save_project_removes_temp_file_when_serialization_fails
FAILED tests/io/test_project_store.py::test_load_project_rejects_bool_for_numeric_cue_fields[id-True]
FAILED tests/io/test_project_store.py::test_load_project_rejects_bool_for_numeric_cue_fields[start-False]
FAILED tests/io/test_project_store.py::test_load_project_rejects_bool_for_numeric_cue_fields[end-True]
FAILED tests/io/test_project_store.py::test_load_project_rejects_bool_for_numeric_cue_fields[confidence-False]
5 failed, 3 passed in 0.39s
```

#### 2. Green phase: verify focused tests pass after the fix

Commands:

```powershell
python -m pytest tests/io/test_script_reader.py -q
python -m pytest tests/io/test_project_store.py -q
```

Outputs:

```text
.....                                                                    [100%]
5 passed in 0.08s
```

```text
........                                                                 [100%]
8 passed in 0.12s
```

#### 3. Full IO verification after the fix

Command:

```powershell
python -m pytest tests/io -q
```

Output:

```text
.............                                                            [100%]
13 passed in 0.15s
```
