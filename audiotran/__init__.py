from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
_src_package = Path(__file__).resolve().parent.parent / "src" / "audiotran"
if _src_package.is_dir():
    _src_path = str(_src_package)
    if _src_path not in __path__:
        __path__.append(_src_path)

__version__ = "0.1.0"
