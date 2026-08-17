# Task 4 Report

Date: 2026-08-17

## Scope

Implemented subtitle segmentation, cue splitting, and script-to-ASR alignment for the Audio Subtitle Tool task brief.

## Changed files

- `src/audiotran/subtitles/__init__.py`
- `src/audiotran/subtitles/alignment.py`
- `src/audiotran/subtitles/segmenter.py`
- `tests/subtitles/test_alignment.py`
- `tests/subtitles/test_segmenter.py`

## Summary of work

- Added `segment_text(text: str, max_chars: int = 22) -> list[str]` with sentence-first splitting on `。！？` and newlines, then fallback splitting on `、` and whitespace before hard slicing.
- Added `align_script(script_segments: list[str], recognized_segments: list[SubtitleCue]) -> list[SubtitleCue]` using normalized text comparison plus `difflib.SequenceMatcher` confidence scoring.
- Added `split_long_cue(cue: SubtitleCue, max_chars: int = 22) -> list[SubtitleCue]` to divide oversized cues across contiguous proportional time spans.
- Added subtitle tests covering segmentation boundaries, normalization preservation, exact and fuzzy alignment, low-confidence mismatches, recognized-text preservation, and proportional split timing.

## Commands and outputs

### 1. Read the task brief

Command:

```powershell
Get-Content D:\audiotran\.superpowers\sdd\2026-08-17-audio-subtitle-tool\task-4-brief.md
```

Output:

```text
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
```

### 2. Red phase: verify failing segmentation tests

Command:

```powershell
python -m pytest tests/subtitles/test_segmenter.py -q
```

Output:

```text
FFFF                                                                     [100%]
================================== FAILURES ===================================
________________ test_segment_text_prefers_sentence_boundaries ________________

    def test_segment_text_prefers_sentence_boundaries():
>       from audiotran.subtitles import segment_text
E       ModuleNotFoundError: No module named 'audiotran.subtitles'

tests\subtitles\test_segmenter.py:9: ModuleNotFoundError
__________ test_segment_text_splits_long_text_without_empty_segments __________

    def test_segment_text_splits_long_text_without_empty_segments():
>       from audiotran.subtitles import segment_text
E       ModuleNotFoundError: No module named 'audiotran.subtitles'

tests\subtitles\test_segmenter.py:21: ModuleNotFoundError
____________ test_segment_text_returns_no_segments_for_empty_lines ____________

    def test_segment_text_returns_no_segments_for_empty_lines():
>       from audiotran.subtitles import segment_text
E       ModuleNotFoundError: No module named 'audiotran.subtitles'

tests\subtitles\test_segmenter.py:34: ModuleNotFoundError
__ test_segment_text_preserves_non_whitespace_text_once_after_normalization ___

    def test_segment_text_preserves_non_whitespace_text_once_after_normalization():
>       from audiotran.subtitles import segment_text
E       ModuleNotFoundError: No module named 'audiotran.subtitles'

tests\subtitles\test_segmenter.py:41: ModuleNotFoundError
=========================== short test summary info ============================
FAILED tests/subtitles/test_segmenter.py::test_segment_text_prefers_sentence_boundaries
FAILED tests/subtitles/test_segmenter.py::test_segment_text_splits_long_text_without_empty_segments
FAILED tests/subtitles/test_segmenter.py::test_segment_text_returns_no_segments_for_empty_lines
FAILED tests/subtitles/test_segmenter.py::test_segment_text_preserves_non_whitespace_text_once_after_normalization
4 failed in 0.22s
```

### 3. Red phase: verify failing alignment tests

Command:

```powershell
python -m pytest tests/subtitles/test_alignment.py -q
```

Output:

```text
FFFFF                                                                    [100%]
================================== FAILURES ===================================
________________ test_align_script_copies_exact_match_into_cue ________________

    def test_align_script_copies_exact_match_into_cue():
>       from audiotran.subtitles.alignment import align_script
E       ModuleNotFoundError: No module named 'audiotran.subtitles.alignment'

tests\subtitles\test_alignment.py:30: ModuleNotFoundError
_____________ test_align_script_accepts_small_suffix_differences ______________

    def test_align_script_accepts_small_suffix_differences():
>       from audiotran.subtitles.alignment import align_script
E       ModuleNotFoundError: No module named 'audiotran.subtitles.alignment'

tests\subtitles\test_alignment.py:43: ModuleNotFoundError
_______ test_align_script_marks_weak_match_without_dropping_script_text _______

    def test_align_script_marks_weak_match_without_dropping_script_text():
>       from audiotran.subtitles.alignment import align_script
E       ModuleNotFoundError: No module named 'audiotran.subtitles.alignment'

tests\subtitles\test_alignment.py:56: ModuleNotFoundError
________ test_align_script_preserves_recognized_text_for_multiple_cues ________

    def test_align_script_preserves_recognized_text_for_multiple_cues():
>       from audiotran.subtitles.alignment import align_script
E       ModuleNotFoundError: No module named 'audiotran.subtitles.alignment'

tests\subtitles\test_alignment.py:70: ModuleNotFoundError
_______________ test_split_long_cue_divides_span_proportionally _______________

    def test_split_long_cue_divides_span_proportionally():
>       from audiotran.subtitles.alignment import split_long_cue
E       ModuleNotFoundError: No module named 'audiotran.subtitles.alignment'

tests\subtitles\test_alignment.py:84: ModuleNotFoundError
=========================== short test summary info ============================
FAILED tests/subtitles/test_alignment.py::test_align_script_copies_exact_match_into_cue
FAILED tests/subtitles/test_alignment.py::test_align_script_accepts_small_suffix_differences
FAILED tests/subtitles/test_alignment.py::test_align_script_marks_weak_match_without_dropping_script_text
FAILED tests/subtitles/test_alignment.py::test_align_script_preserves_recognized_text_for_multiple_cues
FAILED tests/subtitles/test_alignment.py::test_split_long_cue_divides_span_proportionally
5 failed in 0.26s
```

### 4. Green phase: verify subtitle tests pass after implementation

Command:

```powershell
python -m pytest tests/subtitles -q
```

Output:

```text
.........                                                                [100%]
9 passed in 0.06s
```

### 5. Commit the scoped Task 4 changes

Command:

```powershell
git add src/audiotran/subtitles tests/subtitles && git commit -m "feat: segment and align subtitle cues"
```

Output:

```text
warning: in the working copy of 'src/audiotran/subtitles/__init__.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/audiotran/subtitles/alignment.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/audiotran/subtitles/segmenter.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/subtitles/test_alignment.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/subtitles/test_segmenter.py', LF will be replaced by CRLF the next time Git touches it
[main b5297ec] feat: segment and align subtitle cues
 5 files changed, 340 insertions(+)
 create mode 100644 src/audiotran/subtitles/__init__.py
 create mode 100644 src/audiotran/subtitles/alignment.py
 create mode 100644 src/audiotran/subtitles/segmenter.py
 create mode 100644 tests/subtitles/test_alignment.py
 create mode 100644 tests/subtitles/test_segmenter.py
```

### 6. Fresh verification after commit

Commands:

```powershell
python -m pytest tests/subtitles -q
git rev-parse HEAD
git show --stat --oneline --no-patch HEAD
git status --short
```

Outputs:

```text
.........                                                                [100%]
9 passed in 0.05s
```

```text
b5297ec14c49a924f1d3092a3e392b122e0a32cf
```

```text
b5297ec feat: segment and align subtitle cues
```

```text
?? "\343\202\267\343\202\263\343\202\211\343\201\233\350\245\277\345\216\237\343\201\225\343\202\223/"
```

## Commit

- Short hash: `b5297ec`
- Full hash: `b5297ec14c49a924f1d3092a3e392b122e0a32cf`
- Message: `feat: segment and align subtitle cues`

## Concerns

- The repository still has one unrelated untracked directory after this task. I did not stage or modify it.
- Git emitted line-ending warnings during staging and commit (`LF` to `CRLF` on next touch). The commit succeeded and the subtitle tests stayed green, but the repository may want an explicit line-ending policy later.
- `align_script()` preserves unmatched extra script segments by creating zero-duration script-only cues at the last known timestamp. That keeps the text visible instead of discarding it, but downstream UX may want a different review flow for those placeholders.

## Fix Round 1

Date: 2026-08-17

### Scope

Addressed reviewer findings for Task 4:

- Replaced positional `align_script()` zipping with monotonic similarity-based alignment that can skip unmatched script or recognized segments without shifting later matches.
- Explicitly marks unmatched recognized cues with `source="script"`, `japanese_script=""`, and `confidence=0.0` while preserving ASR text and timestamps.
- Reworked `split_long_cue()` so both Japanese fields are split to a common safe segment count, preserving the original cue span and keeping each segment within `max_chars`.
- Added regression tests for middle-gap alignment, extra recognized cues, different split counts, overlong recognized text, and sequential IDs/timestamps after splitting.

### Commands and outputs

#### 1. Red phase: verify reviewer regression tests fail before the fix

Command:

```powershell
python -m pytest tests/subtitles/test_alignment.py -q
```

Output:

```text
....FF.FF                                                                [100%]
================================== FAILURES ===================================
_ test_align_script_skips_missing_script_segment_in_middle_without_shifting_later_matches _

>       assert [cue.japanese_script for cue in aligned] == ["一番目", "", "三番目"]
E       AssertionError: assert ['一番目', '三番目', ''] == ['一番目', '', '三番目']

_________ test_align_script_marks_extra_recognized_cues_as_unmatched __________

>       assert aligned[1].source == "script"
E       AssertionError: assert 'asr' == 'script'

_ test_split_long_cue_handles_different_script_and_recognized_segment_counts __

>       assert len(split) == 3
E       AssertionError: assert 1 == 3

_ test_split_long_cue_splits_overlong_recognized_text_even_when_script_is_short _

>       assert len(split) == 3
E       AssertionError: assert 1 == 3

=========================== short test summary info ============================
FAILED tests/subtitles/test_alignment.py::test_align_script_skips_missing_script_segment_in_middle_without_shifting_later_matches
FAILED tests/subtitles/test_alignment.py::test_align_script_marks_extra_recognized_cues_as_unmatched
FAILED tests/subtitles/test_alignment.py::test_split_long_cue_handles_different_script_and_recognized_segment_counts
FAILED tests/subtitles/test_alignment.py::test_split_long_cue_splits_overlong_recognized_text_even_when_script_is_short
4 failed, 5 passed in 0.27s
```

#### 2. Green phase: verify focused alignment tests pass after the fix

Command:

```powershell
python -m pytest tests/subtitles/test_alignment.py -q
```

Output:

```text
.........                                                                [100%]
9 passed in 0.08s
```

#### 3. Full subtitle verification after the fix

Command:

```powershell
python -m pytest tests/subtitles -q
```

Output:

```text
.............                                                            [100%]
13 passed in 0.06s
```
