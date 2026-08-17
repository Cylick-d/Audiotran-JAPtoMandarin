from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from audiotran.domain.models import SubtitleCue

SubtitleMode = Literal["zh", "bilingual"]


@dataclass(slots=True, frozen=True)
class SubtitleStyle:
    font_name: str
    font_size: int
    primary_color: str
    outline_color: str
    back_color: str
    bold: bool = False
    italic: bool = False
    alignment: int = 2
    margin_l: int = 20
    margin_r: int = 20
    margin_v: int = 20
    outline: int = 2
    shadow: int = 0


def render_srt(cues: list[SubtitleCue], mode: SubtitleMode) -> str:
    blocks: list[str] = []
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    str(cue.id),
                    f"{_format_srt_timestamp(cue.start)} --> {_format_srt_timestamp(cue.end)}",
                    _render_text(cue, mode, srt=True),
                ]
            )
        )
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def render_ass(cues: list[SubtitleCue], mode: SubtitleMode, style: SubtitleStyle) -> str:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        (
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,"
            "ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
            "MarginR,MarginV,Encoding"
        ),
        _render_style(style),
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for cue in cues:
        lines.append(
            "Dialogue: 0,"
            f"{_format_ass_timestamp(cue.start)},{_format_ass_timestamp(cue.end)},"
            f"Default,,0,0,0,,{_render_text(cue, mode, srt=False)}"
        )
    return "\n".join(lines) + "\n"


def _render_style(style: SubtitleStyle) -> str:
    return (
        "Style: Default,"
        f"{style.font_name},{style.font_size},{style.primary_color},&H000000FF,"
        f"{style.outline_color},{style.back_color},{_ass_bool(style.bold)},"
        f"{_ass_bool(style.italic)},0,0,100,100,0,0,1,{style.outline},"
        f"{style.shadow},{style.alignment},{style.margin_l},{style.margin_r},"
        f"{style.margin_v},1"
    )


def _ass_bool(value: bool) -> int:
    return -1 if value else 0


def _render_text(cue: SubtitleCue, mode: SubtitleMode, srt: bool) -> str:
    lines = [cue.chinese] if mode == "zh" else [cue.japanese_script, cue.chinese]
    if srt:
        return "\n".join(lines)
    return "\\N".join(_escape_ass_text(line) for line in lines)


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _format_srt_timestamp(seconds: float) -> str:
    total_milliseconds = _round_half_up(seconds * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _format_ass_timestamp(seconds: float) -> str:
    total_centiseconds = _round_half_up(seconds * 100)
    hours, remainder = divmod(total_centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _round_half_up(value: float) -> int:
    return int(value + 0.5)
