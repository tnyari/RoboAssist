from offline_stt.worker_bootstrap import _safe_error_detail


def test_worker_bootstrap_error_keeps_safe_detail() -> None:
    detail = _safe_error_detail(ImportError("DLL load failed while importing _core"))

    assert detail == "ImportError: DLL load failed while importing _core"


def test_worker_bootstrap_error_redacts_windows_paths() -> None:
    detail = _safe_error_detail(ImportError("Failed to load C:\\Users\\Alice\\audio.wav"))

    assert detail == "ImportError: local path omitted"
