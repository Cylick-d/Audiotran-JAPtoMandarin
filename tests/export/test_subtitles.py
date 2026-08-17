from __future__ import annotations

from audiotran.domain.models import SubtitleCue


def make_cues() -> list[SubtitleCue]:
    return [
        SubtitleCue(
            id=1,
            start=1.234,
            end=3.5,
            japanese_script="最初の行",
            japanese_recognized="最初の行",
            chinese="第一行",
            confidence=0.98,
            source="script",
            reviewed=True,
        ),
        SubtitleCue(
            id=2,
            start=61.0,
            end=62.345,
            japanese_script="brace{test}\\tail",
            japanese_recognized="brace{test}\\tail",
            chinese="第二行",
            confidence=0.95,
            source="asr",
            reviewed=False,
        ),
    ]


def test_render_srt_formats_timestamps_for_chinese_only():
    from audiotran.export.subtitles import render_srt

    assert render_srt(make_cues(), mode="zh") == (
        "1\n"
        "00:00:01,234 --> 00:00:03,500\n"
        "第一行\n\n"
        "2\n"
        "00:01:01,000 --> 00:01:02,345\n"
        "第二行\n"
    )


def test_render_srt_renders_bilingual_text_on_two_lines():
    from audiotran.export.subtitles import render_srt

    assert render_srt(make_cues(), mode="bilingual") == (
        "1\n"
        "00:00:01,234 --> 00:00:03,500\n"
        "最初の行\n"
        "第一行\n\n"
        "2\n"
        "00:01:01,000 --> 00:01:02,345\n"
        "brace{test}\\tail\n"
        "第二行\n"
    )


def test_render_ass_includes_style_and_escapes_special_characters():
    from audiotran.export.subtitles import SubtitleStyle, render_ass

    style = SubtitleStyle(
        font_name="Noto Sans CJK SC",
        font_size=28,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        back_color="&H64000000",
        bold=True,
        italic=False,
        alignment=2,
        margin_l=24,
        margin_r=24,
        margin_v=32,
        outline=2,
        shadow=1,
    )

    rendered = render_ass(make_cues(), mode="bilingual", style=style)

    assert "[V4+ Styles]" in rendered
    assert (
        "Style: Default,Noto Sans CJK SC,28,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,2,1,2,24,24,32,1"
    ) in rendered
    assert "Dialogue: 0,0:00:01.23,0:00:03.50,Default,,0,0,0,,最初の行\\N第一行" in rendered
    assert (
        "Dialogue: 0,0:01:01.00,0:01:02.35,Default,,0,0,0,,brace\\{test\\}\\\\tail\\N第二行"
    ) in rendered


def test_render_ass_renders_chinese_only_without_japanese_line():
    from audiotran.export.subtitles import SubtitleStyle, render_ass

    style = SubtitleStyle(
        font_name="Noto Sans CJK SC",
        font_size=28,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        back_color="&H64000000",
    )

    rendered = render_ass(make_cues(), mode="zh", style=style)

    assert "[Events]" in rendered
    assert "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text" in rendered
    assert (
        "Style: Default,Noto Sans CJK SC,28,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1"
    ) in rendered
    assert "Dialogue: 0,0:00:01.23,0:00:03.50,Default,,0,0,0,,第一行" in rendered
    assert "Dialogue: 0,0:01:01.00,0:01:02.35,Default,,0,0,0,,第二行" in rendered
    assert "最初の行\\N第一行" not in rendered
    assert "brace\\{test\\}\\\\tail\\N第二行" not in rendered


def test_bilingual_renderers_fall_back_to_recognized_text_for_asr_only_cues():
    from audiotran.export.subtitles import SubtitleStyle, render_ass, render_srt

    cue = SubtitleCue(
        id=1,
        start=0.0,
        end=1.0,
        japanese_script="",
        japanese_recognized="ASR recognized text",
        chinese="translated text",
        confidence=None,
        source="asr",
        reviewed=False,
    )
    style = SubtitleStyle(
        font_name="Arial",
        font_size=28,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        back_color="&H00000000",
    )

    assert "ASR recognized text\ntranslated text" in render_srt([cue], mode="bilingual")
    assert "ASR recognized text\\Ntranslated text" in render_ass(
        [cue], mode="bilingual", style=style
    )
