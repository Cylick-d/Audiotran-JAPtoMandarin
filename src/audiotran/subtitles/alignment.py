from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher
from itertools import zip_longest

from audiotran.domain import SubtitleCue

from .segmenter import segment_text

NORMALIZATION_TABLE = str.maketrans("", "", " \t\r\n　、。！？")


def align_script(
    script_segments: list[str], recognized_segments: list[SubtitleCue]
) -> list[SubtitleCue]:
    aligned: list[SubtitleCue] = []

    for script_text, cue in zip(script_segments, recognized_segments):
        aligned.append(
            replace(
                cue,
                japanese_script=script_text,
                confidence=_similarity(script_text, cue.japanese_recognized),
                source="script",
            )
        )

    if len(recognized_segments) > len(script_segments):
        aligned.extend(recognized_segments[len(script_segments) :])

    if len(script_segments) > len(recognized_segments):
        aligned.extend(_build_unmatched_script_cues(script_segments[len(recognized_segments) :], recognized_segments))

    return aligned


def split_long_cue(cue: SubtitleCue, max_chars: int = 22) -> list[SubtitleCue]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")

    script_segments = _segments_or_empty(cue.japanese_script, max_chars)
    recognized_segments = _segments_or_empty(cue.japanese_recognized, max_chars)
    text_segments = script_segments or recognized_segments

    if len(text_segments) <= 1:
        return [cue]

    total_units = sum(_segment_units(segment) for segment in text_segments)
    if total_units == 0:
        return [cue]

    split_cues: list[SubtitleCue] = []
    start = cue.start
    for index, segment in enumerate(text_segments):
        units = _segment_units(segment)
        end = cue.end if index == len(text_segments) - 1 else start + cue.duration() * (units / total_units)
        split_cues.append(
            replace(
                cue,
                id=cue.id + index,
                start=start,
                end=end,
                japanese_script=script_segments[index] if script_segments else "",
                japanese_recognized=recognized_segments[index] if recognized_segments else "",
            )
        )
        start = end

    return split_cues


def _build_unmatched_script_cues(
    script_segments: list[str], recognized_segments: list[SubtitleCue]
) -> list[SubtitleCue]:
    if recognized_segments:
        anchor = recognized_segments[-1]
        next_id = anchor.id + 1
        start = end = anchor.end
    else:
        next_id = 1
        start = end = 0.0

    unmatched: list[SubtitleCue] = []
    for offset, script_text in enumerate(script_segments):
        unmatched.append(
            SubtitleCue(
                id=next_id + offset,
                start=start,
                end=end,
                japanese_script=script_text,
                japanese_recognized="",
                chinese="",
                confidence=0.0,
                source="script",
                reviewed=False,
            )
        )
    return unmatched


def _segments_or_empty(text: str, max_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    return segment_text(cleaned, max_chars=max_chars)


def _segment_units(text: str) -> int:
    return len(_normalize(text))


def _normalize(text: str) -> str:
    return text.translate(NORMALIZATION_TABLE)


def _similarity(left: str, right: str) -> float:
    normalized_left = _normalize(left)
    normalized_right = _normalize(right)
    if not normalized_left and not normalized_right:
        return 1.0
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(a=normalized_left, b=normalized_right).ratio()
