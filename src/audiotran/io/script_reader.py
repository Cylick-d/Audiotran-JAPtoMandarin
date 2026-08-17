from __future__ import annotations

from pathlib import Path


class ScriptEncodingError(ValueError):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"unable to decode script file: {path}")


def read_script(path: Path) -> str:
    path = Path(path)
    payload = path.read_bytes()

    for encoding in ("utf-8-sig", "utf-8", "shift_jis", "utf-16"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ScriptEncodingError(path)
