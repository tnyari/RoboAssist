from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from offline_stt.audio.microphone import InputDevice
from offline_stt.config import Config
from offline_stt.pipeline.types import TranscriptEvent
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
        help_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "Súgó")
        about_action = next(action for action in help_menu.actions() if action.text() == "Névjegy")
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
