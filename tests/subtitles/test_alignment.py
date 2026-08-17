from __future__ import annotations

import pytest

from audiotran.domain import SubtitleCue


def make_cue(
    cue_id: int,
    *,
    start: float = 0.0,
    end: float = 1.0,
    recognized: str,
    script: str = "",
) -> SubtitleCue:
    return SubtitleCue(
        id=cue_id,
        start=start,
        end=end,
        japanese_script=script,
        japanese_recognized=recognized,
        chinese="",
        confidence=None,
        source="asr",
        reviewed=False,
    )


def test_align_script_copies_exact_match_into_cue():
    from audiotran.subtitles.alignment import align_script

    cue = make_cue(1, recognized="こんにちは")

    [aligned] = align_script(["こんにちは"], [cue])

    assert aligned.japanese_script == "こんにちは"
    assert aligned.japanese_recognized == "こんにちは"
    assert aligned.source == "script"
    assert aligned.confidence == pytest.approx(1.0)


def test_align_script_accepts_small_suffix_differences():
    from audiotran.subtitles.alignment import align_script

    cue = make_cue(2, recognized="おはようございますね")

    [aligned] = align_script(["おはようございます"], [cue])

    assert aligned.japanese_script == "おはようございます"
    assert aligned.japanese_recognized == "おはようございますね"
    assert aligned.confidence is not None
    assert aligned.confidence >= 0.8


def test_align_script_marks_weak_match_without_dropping_script_text():
    from audiotran.subtitles.alignment import align_script

    cue = make_cue(3, recognized="ありがとうございます")

    [aligned] = align_script(["さようなら"], [cue])

    assert aligned.japanese_script == "さようなら"
    assert aligned.japanese_recognized == "ありがとうございます"
    assert aligned.source == "script"
    assert aligned.confidence is not None
    assert aligned.confidence < 0.5


def test_align_script_preserves_recognized_text_for_multiple_cues():
    from audiotran.subtitles.alignment import align_script

    cues = [
        make_cue(4, start=0.0, end=1.0, recognized="はい"),
        make_cue(5, start=1.0, end=2.0, recognized="いいえ"),
    ]

    aligned = align_script(["はい", "いいえ"], cues)

    assert [cue.japanese_recognized for cue in aligned] == ["はい", "いいえ"]
    assert [cue.japanese_script for cue in aligned] == ["はい", "いいえ"]


def test_split_long_cue_divides_span_proportionally():
    from audiotran.subtitles.alignment import split_long_cue

    cue = make_cue(6, start=10.0, end=14.0, recognized="あいうえおかきく")

    split = split_long_cue(cue, max_chars=4)

    assert [part.japanese_recognized for part in split] == ["あいうえ", "おかきく"]
    assert split[0].start == pytest.approx(10.0)
    assert split[0].end == pytest.approx(12.0)
    assert split[1].start == pytest.approx(12.0)
    assert split[1].end == pytest.approx(14.0)
    assert split[0].source == "asr"
    assert split[1].source == "asr"
