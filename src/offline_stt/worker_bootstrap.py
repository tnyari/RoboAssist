"""Minimal spawn target that initializes PyAV before unpickling app factories."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.synchronize import Event as ProcessEvent


def run_session_bootstrap(payload: bytes, stop: ProcessEvent, output: Connection) -> None:
    """Load native audio dependencies before app modules can load Python OpenSSL."""
    try:
        from offline_stt.native_deps import initialize_av_runtime

        initialize_av_runtime()
        import pickle

        session_id, config, source_factory, engine_factory = pickle.loads(payload)
        from offline_stt.pipeline.worker import run_session
    except Exception as exc:
        output.send(("error", f"Session worker initialization failed: {_safe_error_detail(exc)}"))
        output.send(("done", None))
        output.close()
        return

    run_session(session_id, config, source_factory, engine_factory, stop, output)


def _safe_error_detail(exc: Exception) -> str:
    """Preserve useful startup details without returning a local path over IPC."""
    detail = str(exc).replace("\r", " ").replace("\n", " ")
    if re.search(r"(?:[A-Za-z]:[\\/]|\\\\)", detail):
        detail = "local path omitted"
    if not detail:
        detail = "no additional detail"
    return f"{type(exc).__name__}: {detail}"[:512]
