import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from offline_stt.audio.microphone import InputDevice
from offline_stt.config import Config
from offline_stt.pipeline.types import PipelineStats, TranscriptEvent
from offline_stt.system_metrics import ProcessUsageSample, ProcessUsageSummary
from offline_stt.ui import window as window_module
from offline_stt.ui.window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


def _primary_background(window, app):
    window.show()
    app.processEvents()
    image = window._start_button.grab().toImage()
    return image.pixelColor(image.width() - 8, image.height() // 2).name()


def test_window_exposes_session_controls_and_renders_partial_and_final(qt_app, monkeypatch):
    device = InputDevice(0, "Teszt mikrofon", "WASAPI", 1, 48000.0, True)
    settings = type(
        "MemorySettings",
        (),
        {
            "value": lambda self, _key, default=None, *_args: default,
            "setValue": lambda self, _key, _value: None,
        },
    )()
    monkeypatch.setattr(window_module, "input_devices", lambda: [device])
    monkeypatch.setattr(window_module.MainWindow, "_settings", property(lambda _self: settings))
    window = MainWindow(
        Config(),
        Path("models/manifest.json"),
        Path("models/cache"),
        (("Base", "base-multilingual"),),
    )
    try:
        help_menu = window.menuBar().actions()[0].menu()
        assert help_menu.title() == "Súgó"
        about_action = help_menu.actions()[0]
        assert about_action.text() == "Névjegy"
        about_dialogs = []
        monkeypatch.setattr(
            window_module.QMessageBox,
            "about",
            lambda _parent, title, text: about_dialogs.append((title, text)),
        )
        about_action.trigger()
        assert about_dialogs[0][0] == "Névjegy – RoboAssist"
        assert "FFmpeg" in about_dialogs[0][1] and "LGPLv2.1" in about_dialogs[0][1]
        assert "_internal/licenses/upstream-sources" in about_dialogs[0][1]
        assert window._start_button.isEnabled()
        assert _primary_background(window, qt_app) == "#1769d2"
        assert not window._stop_button.isEnabled()
        assert window._device_combo.currentData() == 0
        assert window._model_combo.currentData() == "base-multilingual"
        window._buffer.accept(
            TranscriptEvent(1, "s", "s:1", 1, "microphone", "hu", "partial", 0, 1000, "Jó nap", 10)
        )
        window._buffer.accept(
            TranscriptEvent(1, "s", "s:1", 2, "microphone", "hu", "final", 0, 1000, "Jó napot", 20)
        )
        window._render_transcript()
        assert window._transcript.toPlainText() == "Jó napot"
        assert window._copy_button.isEnabled()
        assert window._export_button.isEnabled()
    finally:
        window._poller.stop()
        window._thread.quit()
        assert window._thread.wait(2000)
        window._allow_close = True
        window.close()
        qt_app.processEvents()


def test_start_button_looks_disabled_without_a_local_model(qt_app, monkeypatch):
    device = InputDevice(0, "Teszt mikrofon", "WASAPI", 1, 48000.0, True)
    settings = type(
        "MemorySettings",
        (),
        {
            "value": lambda self, _key, default=None, *_args: default,
            "setValue": lambda self, _key, _value: None,
        },
    )()
    monkeypatch.setattr(window_module, "input_devices", lambda: [device])
    monkeypatch.setattr(window_module.MainWindow, "_settings", property(lambda _self: settings))
    window = MainWindow(
        Config(),
        Path("models/manifest.json"),
        Path("models/cache"),
        (),
    )
    try:
        assert not window._start_button.isEnabled()
        assert _primary_background(window, qt_app) == "#f0f2f5"
    finally:
        window._poller.stop()
        window._thread.quit()
        assert window._thread.wait(2000)
        window._allow_close = True
        window.close()
        qt_app.processEvents()


def test_presentation_callback_runs_after_transcript_paint(qt_app, monkeypatch):
    device = InputDevice(0, "Teszt mikrofon", "WASAPI", 1, 48000.0, True)
    settings = type(
        "MemorySettings",
        (),
        {
            "value": lambda self, _key, default=None, *_args: default,
            "setValue": lambda self, _key, _value: None,
        },
    )()
    monkeypatch.setattr(window_module, "input_devices", lambda: [device])
    monkeypatch.setattr(window_module.MainWindow, "_settings", property(lambda _self: settings))
    presented = []
    stats_snapshots = []
    window = MainWindow(
        Config(),
        Path("models/manifest.json"),
        Path("models/cache"),
        (("Base", "base-multilingual"),),
        presentation_callback=lambda event, timestamp: presented.append((event, timestamp)),
        stats_callback=stats_snapshots.append,
    )
    event = TranscriptEvent(
        1, "session", "session:1", 1, "wav", "hu", "final", 0, 1000, "Jó napot", 10
    )
    try:
        window.show()
        qt_app.processEvents()
        window._poll_session()
        assert stats_snapshots
        assert window._buffer.accept(event)
        window._pending_presentations[event.segment_id] = event
        window._render_transcript()
        window._transcript.repaint()
        qt_app.processEvents()

        assert len(presented) == 1
        assert presented[0][0] == event
        assert presented[0][1] > 0
    finally:
        window._poller.stop()
        window._thread.quit()
        assert window._thread.wait(2000)
        window._allow_close = True
        window.close()
        qt_app.processEvents()


def test_performance_panel_shows_session_and_process_metrics(qt_app, monkeypatch):
    device = InputDevice(0, "Teszt mikrofon", "WASAPI", 1, 48000.0, True)
    settings = type(
        "MemorySettings",
        (),
        {
            "value": lambda self, _key, default=None, *_args: default,
            "setValue": lambda self, _key, _value: None,
        },
    )()
    monkeypatch.setattr(window_module, "input_devices", lambda: [device])
    monkeypatch.setattr(window_module.MainWindow, "_settings", property(lambda _self: settings))
    sample_ready = threading.Event()
    sampler_thread_ids: list[int] = []
    main_thread_id = threading.get_ident()

    class FakeProcessTreeSampler:
        def sample(self):
            sampler_thread_ids.append(threading.get_ident())
            sample_ready.set()
            return ProcessUsageSample(time.monotonic_ns(), 2, 16 * 1_048_576, 12.34)

        @property
        def summary(self):
            return ProcessUsageSummary(8.0, 20 * 1_048_576, 2, 1)

    monkeypatch.setattr(window_module, "ProcessTreeSampler", FakeProcessTreeSampler)
    window = MainWindow(
        Config(),
        Path("models/manifest.json"),
        Path("models/cache"),
        (("Base", "base-multilingual"),),
    )
    assert window._cpu_value.text() == "—"
    assert window._ram_value.text() == "—"
    assert window._metrics_status.text() == "Folyamatmérés indítása…"
    assert sample_ready.wait(1)
    qt_app.processEvents()
    assert sampler_thread_ids and sampler_thread_ids[0] != main_thread_id
    window._process_metrics_thread.requestInterruption()
    assert window._process_metrics_thread.wait(2000)
    stats = PipelineStats(
        audio_samples=160_000,
        source_started_monotonic_ns=1_000_000_000,
        dropped_frames=6,
        frame_backlog=2,
        max_frame_backlog=3,
        job_backlog=4,
        max_job_backlog=5,
        partial_jobs_dropped=9,
        final_jobs_rejected=10,
        partial_decodes=7,
        final_decodes=8,
        partial_decode_seconds=2.0,
        final_decode_seconds=1.0,
    )
    window._last_stats = stats
    window._render_stats(stats)
    try:
        assert window._rtf_value.text() == "0.30"
        assert window._queue_value.text() == "Frame 2/3 · STT 4/5"
        assert window._dropped_value.text() == "6"
        assert window._decode_value.text() == "7 / 8"
        assert window._dropped_jobs_value.text() == "19"

        sample = ProcessUsageSample(time.monotonic_ns(), 2, 16 * 1_048_576, 12.34)
        summary = ProcessUsageSummary(8.0, 20 * 1_048_576, 2, 1)
        window._on_process_metrics_sample(sample, summary)
        assert window._cpu_value.text() == "12.3%"
        assert window._ram_value.text() == "20 MB"
        assert window._metrics_status.text().startswith("Friss")

        partial = TranscriptEvent(
            1, "session", "segment", 1, "microphone", "hu", "partial", 2_000, 2_500, "Teszt", 1
        )
        assert window._buffer.accept(partial)
        window._pending_presentations[partial.segment_id] = partial
        window._on_transcript_painted(4_500_000_000)
        assert window._partial_latency_value.text() == "1500 / 1500 / 1500"

        final = TranscriptEvent(
            1, "session", "segment", 2, "microphone", "hu", "final", 2_000, 3_000, "Teszt.", 2
        )
        assert window._buffer.accept(final)
        window._pending_presentations[final.segment_id] = final
        window._on_transcript_painted(5_000_000_000)
        assert window._final_latency_value.text() == "1000 / 1000 / 1000"

        stale = ProcessUsageSample(time.monotonic_ns() - 3_000_000_000, 2, 16_000, 12.34)
        window._on_process_metrics_sample(stale, summary)
        assert window._cpu_value.text() == "—"
        assert window._ram_value.text() == "—"
        assert window._metrics_status.text().startswith("Elavult")

        window._on_process_metrics_error("OSError")
        assert window._cpu_value.text() == "—"
        assert window._ram_value.text() == "—"
        assert window._metrics_status.text() == "Folyamatmérés nem érhető el (OSError)"
    finally:
        window._poller.stop()
        window._thread.quit()
        assert window._thread.wait(2000)
        window._allow_close = True
        window.close()
        qt_app.processEvents()
