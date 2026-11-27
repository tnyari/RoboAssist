import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from offline_stt.audio.microphone import InputDevice
from offline_stt.config import Config
from offline_stt.pipeline.types import PipelineStats, TranscriptEvent
from offline_stt.system_metrics import ProcessUsageSample, ProcessUsageSummary
from offline_stt.ui import window as window_module
from offline_stt.ui.window import MainWindow, TranscriptView


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
        assert "FFmpeg 8.1.2" in about_dialogs[0][1] and "LGPLv3" in about_dialogs[0][1]
        assert "LGPLv2.1" not in about_dialogs[0][1]
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


def test_controls_states_copy_export_and_stop_clear_are_explicit(qt_app, monkeypatch):
    device = InputDevice(0, "Teszt mikrofon", "WASAPI", 1, 48000.0, True)
    second_device = InputDevice(1, "Második mikrofon", "WASAPI", 1, 44100.0, False)
    values = {}
    settings = type(
        "MemorySettings",
        (),
        {
            "value": lambda self, key, default=None, *_args: values.get(key, default),
            "setValue": lambda self, key, value: values.__setitem__(key, value),
        },
    )()
    monkeypatch.setattr(window_module, "input_devices", lambda: [device, second_device])
    monkeypatch.setattr(window_module.MainWindow, "_settings", property(lambda _self: settings))
    writes = []

    def track_write(path, data, *args, **kwargs):
        writes.append((path, data, kwargs))

    monkeypatch.setattr(Path, "write_text", track_write)
    window = MainWindow(
        Config(),
        Path("models/manifest.json"),
        Path("models/cache"),
        (("Base", "base-multilingual"), ("Small", "small-multilingual")),
    )
    destination = Path("átirat.txt")
    try:
        start_requests = []
        window.start_requested.connect(lambda *args: start_requests.append(args))
        assert window._language_combo.currentData() == "hu"
        assert window._device_combo.currentData() == 0
        assert window._model_combo.currentData() == "base-multilingual"
        assert window._start_button.isEnabled()
        assert not window._stop_button.isEnabled()
        assert not window._clear_button.isEnabled()
        assert window._capture_state == "idle"
        assert window._controller.snapshot()[2] == "idle"
        assert start_requests == []
        assert window._controller.thread() is window._thread

        window.start_requested.disconnect(window._controller.start)
        window._device_combo.setCurrentIndex(1)
        window._model_combo.setCurrentIndex(1)
        window._language_combo.setCurrentIndex(window._language_combo.findData("en"))
        window._start_button.click()
        assert start_requests == [(1, 44100, "small-multilingual", "en")]
        assert window._capture_state == "loading"
        assert not window._start_button.isEnabled()
        assert not window._device_combo.isEnabled()
        assert not window._model_combo.isEnabled()
        assert not window._language_combo.isEnabled()
        window._start_button.click()
        assert len(start_requests) == 1

        topmost = Qt.WindowType.WindowStaysOnTopHint
        window._always_on_top.setChecked(True)
        assert window.windowFlags() & topmost
        assert values["always_on_top"] is True
        window._always_on_top.setChecked(False)
        assert not window.windowFlags() & topmost

        window._on_state_changed("loading", "Helyi modell betöltése…")
        assert not window._start_button.isEnabled()
        assert not window._stop_button.isEnabled()
        window._on_state_changed("running", "Mikrofon figyel")
        assert window._stop_button.isEnabled()
        window._render_stats(PipelineStats(input_level_dbfs=-18.0, decoder_busy=True))
        assert window._level_bar.value() == 70
        assert window._level_db.text() == "-18 dBFS"
        assert window._status_label.text() == "Beszéd feldolgozása"

        stop_requests = []
        window.stop_requested.disconnect(window._controller.stop)
        window.stop_requested.connect(lambda: stop_requests.append(True))
        window._stop_button.click()
        assert stop_requests == [True]
        assert window._capture_state == "stopping"
        assert not window._stop_button.isEnabled()
        window._stop_button.click()
        assert len(stop_requests) == 1

        event = TranscriptEvent(
            1, "session", "segment", 1, "microphone", "hu", "final", 0, 1000, "Jó napot", 1
        )
        assert window._buffer.accept(event)
        window._render_transcript()
        assert window._copy_button.isEnabled()
        assert window._export_button.isEnabled()
        assert writes == []
        window._copy_transcript()
        assert QApplication.clipboard().text() == "Jó napot"

        monkeypatch.setattr(
            window_module.QFileDialog,
            "getSaveFileName",
            lambda *_args, **_kwargs: (str(destination), "Szövegfájl (*.txt)"),
        )
        window._export_transcript()
        assert writes == [(destination, "Jó napot\n", {"encoding": "utf-8"})]

        window._clear_button.click()
        assert window._buffer.is_empty
        assert not window._copy_button.isEnabled()
        assert not window._export_button.isEnabled()
        next_event = TranscriptEvent(
            1, "session", "segment-2", 1, "microphone", "hu", "final", 1000, 2000, "Köszönöm", 2
        )
        assert window._buffer.accept(next_event)
        window._render_transcript()
        window._on_state_changed("idle", "Leállítva")
        window._on_session_stopped("")
        assert window._buffer.is_empty
        assert window._transcript.toPlainText() == ""
        assert window._status_label.text() == "Leállítva · munkamenet törölve"
        assert not window._stop_button.isEnabled()

        assert window._buffer.accept(event)
        window._on_state_changed("error", "Mikrofonhiba")
        assert window._buffer.is_empty
        assert window._status_label.text() == "Mikrofonhiba"
        assert writes == [(destination, "Jó napot\n", {"encoding": "utf-8"})]
    finally:
        window._poller.stop()
        window._thread.quit()
        assert window._thread.wait(2000)
        window._allow_close = True
        window.close()
        qt_app.processEvents()


def test_transcript_auto_scroll_and_partial_final_styles(qt_app):
    view = TranscriptView()
    view.resize(240, 100)
    view.show()
    qt_app.processEvents()
    buffer = window_module.TranscriptBuffer()
    for index in range(60):
        buffer.accept(
            TranscriptEvent(
                1,
                "session",
                f"segment-{index}",
                1,
                "microphone",
                "hu",
                "partial" if index == 0 else "final",
                float(index * 1000),
                float((index + 1) * 1000),
                "Hosszú magyar próbamondat " * 8,
                float(index),
            )
        )
    view.render_buffer(buffer)
    qt_app.processEvents()
    scroll = view.verticalScrollBar()
    assert scroll.maximum() > 28
    assert scroll.maximum() - scroll.value() < 28
    rendered = view.document().toHtml()
    assert "#8995a5" in rendered
    assert "#172438" in rendered

    scroll.setValue(0)
    qt_app.processEvents()
    buffer.accept(
        TranscriptEvent(
            1,
            "session",
            "later-top",
            1,
            "microphone",
            "hu",
            "final",
            61000,
            62000,
            "Újabb mondat " * 8,
            61,
        )
    )
    view.render_buffer(buffer)
    qt_app.processEvents()
    assert scroll.value() == 0

    scroll.setValue(scroll.maximum())
    qt_app.processEvents()
    buffer.accept(
        TranscriptEvent(
            1,
            "session",
            "later-bottom",
            1,
            "microphone",
            "hu",
            "final",
            62000,
            63000,
            "A végén érkezett mondat " * 8,
            62,
        )
    )
    view.render_buffer(buffer)
    qt_app.processEvents()
    assert scroll.maximum() - scroll.value() < 28
    view.close()
