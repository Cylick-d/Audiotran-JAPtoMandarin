from __future__ import annotations


def _normalize(text: str) -> str:
    return "".join(text.split())


def test_segment_text_prefers_sentence_boundaries():
    from audiotran.subtitles import segment_text

    text = "今日は晴れです。明日も晴れるでしょう！本当ですか？"

    assert segment_text(text, max_chars=12) == [
        "今日は晴れです。",
        "明日も晴れるでしょう！",
        "本当ですか？",
    ]


def test_segment_text_splits_long_text_without_empty_segments():
    from audiotran.subtitles import segment_text

    text = "ひとつ、ふたつ、みっつ、よっつ"

    assert segment_text(text, max_chars=6) == [
        "ひとつ、",
        "ふたつ、",
        "みっつ、",
        "よっつ",
    ]


def test_segment_text_returns_no_segments_for_empty_lines():
    from audiotran.subtitles import segment_text

    assert segment_text("", max_chars=10) == []
    assert segment_text(" \n\t ", max_chars=10) == []


def test_segment_text_preserves_non_whitespace_text_once_after_normalization():
    from audiotran.subtitles import segment_text

    text = "これは とても長い文章で、\n改行や 空白を含みます。まだ続きます。"

    segments = segment_text(text, max_chars=9)

    assert segments
    assert all(segment.strip() for segment in segments)
    assert _normalize("".join(segments)) == _normalize(text)
