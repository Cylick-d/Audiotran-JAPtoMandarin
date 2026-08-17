from __future__ import annotations

BOUNDARY_PUNCTUATION = "。！？\n"
SOFT_BOUNDARIES = "、 \t\r\n"


def segment_text(text: str, max_chars: int = 22) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")

    stripped = text.strip()
    if not stripped:
        return []

    coarse_segments = _split_on_sentence_boundaries(stripped)

    segments: list[str] = []
    for coarse_segment in coarse_segments:
        segments.extend(_split_with_limit(coarse_segment, max_chars))
    return segments


def _split_on_sentence_boundaries(text: str) -> list[str]:
    segments: list[str] = []
    buffer: list[str] = []

    for char in text:
        if char == "\r":
            continue
        buffer.append(char)
        if char in BOUNDARY_PUNCTUATION:
            _append_if_nonempty(segments, "".join(buffer))
            buffer.clear()

    _append_if_nonempty(segments, "".join(buffer))
    return segments


def _split_with_limit(text: str, max_chars: int) -> list[str]:
    remaining = text.strip()
    if not remaining:
        return []

    segments: list[str] = []
    while len(remaining) > max_chars:
        split_at = _find_split_point(remaining, max_chars)
        _append_if_nonempty(segments, remaining[:split_at])
        remaining = remaining[split_at:].lstrip()

    _append_if_nonempty(segments, remaining)
    return segments


def _find_split_point(text: str, max_chars: int) -> int:
    search_limit = min(max_chars, len(text))
    for index in range(search_limit, 0, -1):
        if text[index - 1] in SOFT_BOUNDARIES:
            return index
    return search_limit


def _append_if_nonempty(segments: list[str], text: str) -> None:
    cleaned = text.strip()
    if cleaned:
        segments.append(cleaned)
