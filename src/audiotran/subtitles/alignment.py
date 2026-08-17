from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher
from functools import lru_cache
import math

from audiotran.domain import SubtitleCue

from .segmenter import segment_text

NORMALIZATION_TABLE = str.maketrans("", "", " \t\r\n　、。！？")
UNMATCHED_PENALTY = 0.6


def align_script(
    script_segments: list[str], recognized_segments: list[SubtitleCue]
) -> list[SubtitleCue]:
    operations = _alignment_operations(script_segments, recognized_segments)
    next_synthetic_id = max((cue.id for cue in recognized_segments), default=0) + 1
    aligned: list[SubtitleCue] = []

    index = 0
    while index < len(operations):
        operation, script_index, cue_index = operations[index]
        if operation == "match":
            cue = recognized_segments[cue_index]
            script_text = script_segments[script_index]
            aligned.append(
                replace(
                    cue,
                    japanese_script=script_text,
                    confidence=_similarity(script_text, cue.japanese_recognized),
                    source="script",
                )
            )
            index += 1
            continue

        if operation == "cue":
            cue = recognized_segments[cue_index]
            aligned.append(
                replace(
                    cue,
                    japanese_script="",
                    confidence=0.0,
                    source="script",
                )
            )
            index += 1
            continue

        run_start = index
        while index < len(operations) and operations[index][0] == "script":
            index += 1
        script_run = [script_segments[operations[offset][1]] for offset in range(run_start, index)]
        previous_cue = _last_recognized_cue(aligned)
        next_cue = _next_recognized_cue(operations, index, recognized_segments)
        synthetic_cues, next_synthetic_id = _build_unmatched_script_cues(
            script_run,
            previous_cue,
            next_cue,
            next_synthetic_id,
        )
        aligned.extend(synthetic_cues)

    return aligned


def split_long_cue(cue: SubtitleCue, max_chars: int = 22) -> list[SubtitleCue]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")

    script_base_segments = _segments_or_empty(cue.japanese_script, max_chars)
    recognized_base_segments = _segments_or_empty(cue.japanese_recognized, max_chars)
    target_count = max(len(script_base_segments), len(recognized_base_segments))

    if target_count <= 1:
        return [cue]

    script_segments = _split_text_to_count(cue.japanese_script, max_chars, target_count)
    recognized_segments = _split_text_to_count(cue.japanese_recognized, max_chars, target_count)
    weights = [
        max(_segment_units(script_segment), _segment_units(recognized_segment))
        for script_segment, recognized_segment in zip(script_segments, recognized_segments)
    ]
    total_weight = sum(weights)
    if total_weight == 0:
        return [cue]

    split_cues: list[SubtitleCue] = []
    start = cue.start
    for index, (script_segment, recognized_segment, weight) in enumerate(
        zip(script_segments, recognized_segments, weights)
    ):
        end = (
            cue.end
            if index == target_count - 1
            else start + cue.duration() * (weight / total_weight)
        )
        split_cues.append(
            replace(
                cue,
                id=cue.id + index,
                start=start,
                end=end,
                japanese_script=script_segment,
                japanese_recognized=recognized_segment,
            )
        )
        start = end

    return split_cues


def _alignment_operations(
    script_segments: list[str], recognized_segments: list[SubtitleCue]
) -> list[tuple[str, int | None, int | None]]:
    script_count = len(script_segments)
    cue_count = len(recognized_segments)

    @lru_cache(maxsize=None)
    def best_score(script_index: int, cue_index: int) -> float:
        if script_index == script_count and cue_index == cue_count:
            return 0.0
        if script_index == script_count:
            return -(cue_count - cue_index) * UNMATCHED_PENALTY
        if cue_index == cue_count:
            return -(script_count - script_index) * UNMATCHED_PENALTY

        match_score = _similarity(
            script_segments[script_index],
            recognized_segments[cue_index].japanese_recognized,
        ) + best_score(script_index + 1, cue_index + 1)
        cue_skip_score = -UNMATCHED_PENALTY + best_score(script_index, cue_index + 1)
        script_skip_score = -UNMATCHED_PENALTY + best_score(script_index + 1, cue_index)
        return max(match_score, cue_skip_score, script_skip_score)

    operations: list[tuple[str, int | None, int | None]] = []
    script_index = 0
    cue_index = 0
    while script_index < script_count or cue_index < cue_count:
        if script_index == script_count:
            operations.append(("cue", None, cue_index))
            cue_index += 1
            continue
        if cue_index == cue_count:
            operations.append(("script", script_index, None))
            script_index += 1
            continue

        match_score = _similarity(
            script_segments[script_index],
            recognized_segments[cue_index].japanese_recognized,
        ) + best_score(script_index + 1, cue_index + 1)
        cue_skip_score = -UNMATCHED_PENALTY + best_score(script_index, cue_index + 1)
        script_skip_score = -UNMATCHED_PENALTY + best_score(script_index + 1, cue_index)

        if match_score >= cue_skip_score and match_score >= script_skip_score:
            operations.append(("match", script_index, cue_index))
            script_index += 1
            cue_index += 1
        elif cue_skip_score >= script_skip_score:
            operations.append(("cue", None, cue_index))
            cue_index += 1
        else:
            operations.append(("script", script_index, None))
            script_index += 1

    return operations


def _build_unmatched_script_cues(
    script_segments: list[str],
    previous_cue: SubtitleCue | None,
    next_cue: SubtitleCue | None,
    next_synthetic_id: int,
) -> tuple[list[SubtitleCue], int]:
    count = len(script_segments)
    if count == 0:
        return [], next_synthetic_id

    if previous_cue is not None and next_cue is not None and next_cue.start > previous_cue.end:
        gap = next_cue.start - previous_cue.end
        cues: list[SubtitleCue] = []
        current_start = previous_cue.end
        for index, script_text in enumerate(script_segments):
            current_end = (
                next_cue.start
                if index == count - 1
                else previous_cue.end + gap * ((index + 1) / count)
            )
            cues.append(
                SubtitleCue(
                    id=next_synthetic_id + index,
                    start=current_start,
                    end=current_end,
                    japanese_script=script_text,
                    japanese_recognized="",
                    chinese="",
                    confidence=0.0,
                    source="script",
                    reviewed=False,
                )
            )
            current_start = current_end
        return cues, next_synthetic_id + count

    if next_cue is not None:
        anchor = next_cue.start
    elif previous_cue is not None:
        anchor = previous_cue.end
    else:
        anchor = 0.0

    cues = [
        SubtitleCue(
            id=next_synthetic_id + index,
            start=anchor,
            end=anchor,
            japanese_script=script_text,
            japanese_recognized="",
            chinese="",
            confidence=0.0,
            source="script",
            reviewed=False,
        )
        for index, script_text in enumerate(script_segments)
    ]
    return cues, next_synthetic_id + count


def _last_recognized_cue(cues: list[SubtitleCue]) -> SubtitleCue | None:
    for cue in reversed(cues):
        if cue.japanese_recognized:
            return cue
    return None


def _next_recognized_cue(
    operations: list[tuple[str, int | None, int | None]],
    start_index: int,
    recognized_segments: list[SubtitleCue],
) -> SubtitleCue | None:
    for operation, _script_index, cue_index in operations[start_index:]:
        if operation in {"match", "cue"}:
            return recognized_segments[cue_index]
    return None


def _segments_or_empty(text: str, max_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    return segment_text(cleaned, max_chars=max_chars)


def _split_text_to_count(text: str, max_chars: int, count: int) -> list[str]:
    cleaned = text.strip()
    if count <= 0:
        return []
    if not cleaned:
        return [""] * count

    nonempty_count = min(count, len(cleaned))
    remaining = cleaned
    segments: list[str] = []
    for index in range(nonempty_count):
        remaining_segments = nonempty_count - index
        target_length = math.ceil(len(remaining) / remaining_segments)
        target_length = min(target_length, max_chars)
        segments.append(remaining[:target_length])
        remaining = remaining[target_length:]

    segments.extend([""] * (count - nonempty_count))
    return segments


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
