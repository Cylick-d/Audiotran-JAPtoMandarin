from __future__ import annotations

from pathlib import Path

import pytest

from audiotran.io.script_reader import ScriptEncodingError, read_script


@pytest.mark.parametrize("encoding", ["utf-8", "shift_jis", "utf-16"])
def test_read_script_supports_japanese_text_in_supported_encodings(
    tmp_path: Path, encoding: str
):
    script_path = tmp_path / f"script-{encoding}.txt"
    expected = "字幕テスト\nこんにちは世界"
    script_path.write_bytes(expected.encode(encoding))

    assert read_script(script_path) == expected


def test_read_script_strips_utf8_bom(tmp_path: Path):
    script_path = tmp_path / "script-utf8-bom.txt"
    expected = "字幕テスト\nこんにちは世界"
    script_path.write_bytes(expected.encode("utf-8-sig"))

    assert read_script(script_path) == expected


def test_read_script_raises_when_no_supported_encoding_matches(tmp_path: Path):
    script_path = tmp_path / "script.bin"
    script_path.write_bytes(b"\x81")

    with pytest.raises(ScriptEncodingError) as exc_info:
        read_script(script_path)

    assert exc_info.value.path == script_path
