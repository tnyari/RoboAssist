"""Windows DLL search setup for the separately licensed PyAV runtime."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

_DLL_HANDLES: list[object] = []
_REGISTERED: set[str] = set()


def configure_av_dll_search() -> None:
    """Keep the staged PyAV/FFmpeg DLL directory available to Windows' loader."""
    if sys.platform != "win32":
        return

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates = [Path(frozen_root) / "av.libs"]
    else:
        candidates = [Path(sys.prefix) / "Lib" / "site-packages" / "av.libs"]

    for directory in candidates:
        if not directory.is_dir():
            continue
        key = str(directory.resolve()).casefold()
        if key not in _REGISTERED:
            _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
            _REGISTERED.add(key)


def initialize_av_runtime() -> Any:
    """Load PyAV in the owning process before any worker threads start."""
    configure_av_dll_search()
    return import_module("av")
