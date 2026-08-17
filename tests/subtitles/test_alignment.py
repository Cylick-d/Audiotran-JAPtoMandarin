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


def test_align_script_skips_missing_script_segment_in_middle_without_shifting_later_matches():
    from audiotran.subtitles.alignment import align_script

    cues = [
        make_cue(10, start=0.0, end=1.0, recognized="一番目"),
        make_cue(11, start=1.0, end=2.0, recognized="二番目"),
        make_cue(12, start=2.0, end=3.0, recognized="三番目"),
    ]

    aligned = align_script(["一番目", "三番目"], cues)

    assert [cue.japanese_script for cue in aligned] == ["一番目", "", "三番目"]
    assert [cue.japanese_recognized for cue in aligned] == ["一番目", "二番目", "三番目"]
    assert [cue.confidence for cue in aligned] == pytest.approx([1.0, 0.0, 1.0])


def test_align_script_marks_extra_recognized_cues_as_unmatched():
    from audiotran.subtitles.alignment import align_script

    cues = [
        make_cue(20, start=0.0, end=1.0, recognized="はい"),
        make_cue(21, start=1.0, end=2.0, recognized="余分です"),
    ]

    aligned = align_script(["はい"], cues)

    assert aligned[0].japanese_script == "はい"
    assert aligned[1].japanese_script == ""
    assert aligned[1].japanese_recognized == "余分です"
    assert aligned[1].source == "script"
    assert aligned[1].confidence == pytest.approx(0.0)
    assert aligned[1].start == pytest.approx(1.0)
    assert aligned[1].end == pytest.approx(2.0)


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


def test_split_long_cue_handles_different_script_and_recognized_segment_counts():
    from audiotran.subtitles.alignment import split_long_cue

    cue = make_cue(
        30,
        start=0.0,
        end=9.0,
        recognized="あいうえおかきくけこさし",
        script="短い文",
    )

    split = split_long_cue(cue, max_chars=4)

    assert len(split) == 3
    assert all(len(part.japanese_script) <= 4 for part in split)
    assert all(len(part.japanese_recognized) <= 4 for part in split)
    assert split[0].start == pytest.approx(0.0)
    assert split[-1].end == pytest.approx(9.0)
    assert [part.id for part in split] == [30, 31, 32]
    assert "".join(part.japanese_script for part in split) == "短い文"
    assert "".join(part.japanese_recognized for part in split) == "あいうえおかきくけこさし"


def test_split_long_cue_splits_overlong_recognized_text_even_when_script_is_short():
    from audiotran.subtitles.alignment import split_long_cue

    cue = make_cue(
        40,
        start=5.0,
        end=8.0,
        recognized="ながいながいながい",
        script="短い",
    )

    split = split_long_cue(cue, max_chars=3)

    assert len(split) == 3
    assert all(len(part.japanese_script) <= 3 for part in split)
    assert all(len(part.japanese_recognized) <= 3 for part in split)
    assert split[0].start == pytest.approx(5.0)
    assert split[0].end < split[1].end < split[2].end
    assert split[-1].end == pytest.approx(8.0)
