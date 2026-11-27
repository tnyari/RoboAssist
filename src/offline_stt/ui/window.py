"""Responsive Windows transcript window."""

from __future__ import annotations

import html
import math
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QPaintEvent, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from offline_stt.audio.microphone import InputDevice, input_devices
from offline_stt.config import Config
from offline_stt.metrics import percentile_summary, summarize_pipeline
from offline_stt.pipeline.types import PipelineStats, TranscriptEvent
from offline_stt.system_metrics import (
    ProcessTreeSampler,
    ProcessUsageSample,
    ProcessUsageSummary,
)
from offline_stt.ui.controller import SessionController
from offline_stt.ui.transcript import TranscriptBuffer

_LANGUAGES = (
    ("Magyar", "hu"),
    ("English", "en"),
    ("Čeština", "cs"),
    ("Slovenčina", "sk"),
    ("Română", "ro"),
)


class TranscriptView(QTextBrowser):
    """Transcript browser that timestamps completed Qt paint passes."""

    painted = Signal(object)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        self.painted.emit(time.monotonic_ns())

    def render_buffer(self, buffer: TranscriptBuffer) -> None:
        scroll_bar = self.verticalScrollBar()
        old_scroll = scroll_bar.value()
        was_at_bottom = scroll_bar.maximum() - old_scroll < 28
        pieces = []
        if buffer.truncated:
            pieces.append(
                '<span style="color:#8995a5">… a régebbi feliratok a memóriakorlát '
                "miatt törölve …</span>"
            )
        for text, final in buffer.parts:
            safe = html.escape(text).replace("\n", "<br>")
            if final:
                pieces.append(f'<span style="color:#172438">{safe}</span>')
            else:
                pieces.append(f'<span style="color:#8995a5">{safe}</span>')
        self.setHtml("<div style='line-height:1.65'>" + " ".join(pieces) + "</div>")
        if was_at_bottom:
            self.moveCursor(QTextCursor.MoveOperation.End)
        else:
            scroll_bar.setValue(min(old_scroll, scroll_bar.maximum()))


class _ProcessMetricsThread(QThread):
    sample_ready = Signal(object, object)
    sample_failed = Signal(str)

    def run(self) -> None:
        try:
            sampler = ProcessTreeSampler()
            while not self.isInterruptionRequested():
                sample = sampler.sample()
                self.sample_ready.emit(sample, sampler.summary)
                for _ in range(20):
                    if self.isInterruptionRequested():
                        return
                    self.msleep(50)
        except (OSError, RuntimeError, ValueError) as exc:
            self.sample_failed.emit(type(exc).__name__)


class MainWindow(QMainWindow):
    start_requested = Signal(int, int, str, str)
    stop_requested = Signal()
    close_requested = Signal()

    def __init__(
        self,
        config: Config,
        catalog_path: Path,
        model_root: Path,
        installed_models: tuple[tuple[str, str], ...],
        presentation_callback: Callable[[TranscriptEvent, int], None] | None = None,
        stats_callback: Callable[[PipelineStats], None] | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._catalog_path = catalog_path
        self._model_root = model_root
        self._installed_models = installed_models
        self._devices: list[InputDevice] = []
        self._buffer = TranscriptBuffer()
        self._presentation_callback = presentation_callback
        self._stats_callback = stats_callback
        self._pending_presentations: dict[str, TranscriptEvent] = {}
        self._last_stats = PipelineStats()
        self._partial_latency_samples: deque[float] = deque(maxlen=512)
        self._final_latency_samples: deque[float] = deque(maxlen=512)
        self._partial_latency_segments: deque[str] = deque(maxlen=512)
        self._final_latency_segments: deque[str] = deque(maxlen=512)
        self._partial_latency_ids: set[str] = set()
        self._final_latency_ids: set[str] = set()
        self._process_metrics_sample: ProcessUsageSample | None = None
        self._process_metrics_summary: ProcessUsageSummary | None = None
        self._process_metrics_error: str | None = None
        self._accept_events = False
        self._capture_state = "idle"
        self._closing = False
        self._allow_close = False

        self.setWindowTitle("RoboAssist · offline felirat")
        self.setMinimumSize(680, 560)
        self.resize(940, 720)
        self._restore_settings()
        self._build_ui()
        self._transcript.painted.connect(self._on_transcript_painted)
        if self._always_on_top.isChecked():
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._load_devices()
        self._populate_models()

        self._thread = QThread(self)
        self._controller = SessionController(config, str(catalog_path), str(model_root))
        self._controller.moveToThread(self._thread)
        self.start_requested.connect(self._controller.start)
        self.stop_requested.connect(self._controller.stop)
        self.close_requested.connect(self._controller.close_session)
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.session_started.connect(self._on_session_started)
        self._controller.session_stopped.connect(self._on_session_stopped)
        self._controller.closed.connect(self._on_controller_closed)
        self._controller.closed.connect(self._thread.quit)
        self._thread.finished.connect(self._controller.deleteLater)
        self._thread.start()

        self._poller = QTimer(self)
        self._poller.setInterval(100)
        self._poller.timeout.connect(self._poll_session)
        self._poller.start()
        self._process_metrics_thread = _ProcessMetricsThread(self)
        self._process_metrics_thread.sample_ready.connect(self._on_process_metrics_sample)
        self._process_metrics_thread.sample_failed.connect(self._on_process_metrics_error)
        self._process_metrics_thread.start()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6fa; }
            QFrame#hero { background: #15243a; border-radius: 14px; }
            QLabel#brand { color: #ffffff; font-size: 21px; font-weight: 700; }
            QLabel#tagline { color: #b8c7dc; font-size: 11px; }
            QLabel#status { color: #ffffff; font-size: 13px; font-weight: 600; }
            QLabel#sectionTitle { color: #172438; font-size: 14px; font-weight: 650; }
            QGroupBox { border: 1px solid #dce2eb; border-radius: 10px; margin-top: 9px;
                        padding: 12px; background: #ffffff; color: #334155; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QComboBox { min-height: 34px; border: 1px solid #d5dce7; border-radius: 7px;
                        padding: 2px 9px; background: #ffffff; }
            QPushButton { min-height: 34px; padding: 0 13px; border-radius: 7px;
                          border: 1px solid #d5dce7; background: #ffffff; color: #172438; }
            QPushButton:hover { background: #edf2f8; }
            QPushButton:disabled { color: #9aa5b5; background: #f0f2f5; }
            QPushButton#primary { background: #1769d2; border-color: #1769d2; color: #ffffff;
                                  font-weight: 650; }
            QPushButton#primary:hover { background: #0f58b6; }
            QPushButton#primary:disabled, QPushButton#primary:disabled:hover {
                background: #f0f2f5; border-color: #d5dce7; color: #9aa5b5;
            }
            QTextBrowser { border: 1px solid #dce2eb; border-radius: 10px; background: #ffffff;
                           color: #172438; padding: 16px; selection-background-color: #b7d5ff; }
            QProgressBar { height: 10px; border: 0; border-radius: 5px; background: #e7ebf1; }
            QProgressBar::chunk { border-radius: 5px; background: #27a679; }
            QLabel.metric { color: #5c6879; font-size: 11px; }
            QLabel.metricValue { color: #172438; font-size: 14px; font-weight: 650; }
            """
        )
        help_menu = self.menuBar().addMenu("Súgó")
        about_action = help_menu.addAction("Névjegy")
        about_action.triggered.connect(self._show_about)
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(13)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 15, 18, 15)
        brand_box = QVBoxLayout()
        brand = QLabel("RoboAssist")
        brand.setObjectName("brand")
        tagline = QLabel("HELYI BESZÉDFELISMERÉS  ·  OFFLINE")
        tagline.setObjectName("tagline")
        brand_box.addWidget(brand)
        brand_box.addWidget(tagline)
        hero_layout.addLayout(brand_box)
        hero_layout.addStretch(1)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #94a3b8; font-size: 18px;")
        self._status_label = QLabel("Készen áll")
        self._status_label.setObjectName("status")
        status_box = QHBoxLayout()
        status_box.addWidget(self._status_dot)
        status_box.addWidget(self._status_label)
        hero_layout.addLayout(status_box)
        layout.addWidget(hero)

        settings = QGroupBox("Munkamenet")
        grid = QGridLayout(settings)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Mikrofon"), 0, 0)
        self._device_combo = QComboBox()
        self._device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._device_combo.setAccessibleName("Mikrofon kiválasztása")
        grid.addWidget(self._device_combo, 0, 1)
        self._refresh_devices = QPushButton("Frissítés")
        self._refresh_devices.setToolTip("Újraolvassa a Windows hangbemeneteit")
        self._refresh_devices.clicked.connect(self._load_devices)
        grid.addWidget(self._refresh_devices, 0, 2)
        grid.addWidget(QLabel("Helyi modell"), 1, 0)
        self._model_combo = QComboBox()
        self._model_combo.setAccessibleName("Helyi beszédfelismerő modell")
        grid.addWidget(self._model_combo, 1, 1)
        grid.addWidget(QLabel("Nyelv"), 1, 2)
        self._language_combo = QComboBox()
        for label, code in _LANGUAGES:
            self._language_combo.addItem(label, code)
        language_index = self._language_combo.findData(self._config.application.language)
        self._language_combo.setCurrentIndex(max(0, language_index))
        self._language_combo.setAccessibleName("Besédfelismerés nyelve")
        grid.addWidget(self._language_combo, 1, 3)
        self._always_on_top = QPushButton("Mindig felül")
        self._always_on_top.setCheckable(True)
        self._always_on_top.setAccessibleName("Ablak mindig felül")
        self._always_on_top.setChecked(bool(self._settings.value("always_on_top", False, bool)))
        self._always_on_top.toggled.connect(self._set_always_on_top)
        grid.addWidget(self._always_on_top, 0, 3)
        layout.addWidget(settings)

        level_row = QHBoxLayout()
        self._level_label = QLabel("Bemeneti jelszint")
        self._level_label.setObjectName("sectionTitle")
        level_row.addWidget(self._level_label)
        self._level_bar = QProgressBar()
        self._level_bar.setRange(0, 100)
        self._level_bar.setValue(0)
        self._level_bar.setTextVisible(False)
        self._level_bar.setAccessibleName("Mikrofon bemeneti jelszint")
        level_row.addWidget(self._level_bar, 1)
        self._level_db = QLabel("−∞ dBFS")
        self._level_db.setMinimumWidth(64)
        self._level_db.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        level_row.addWidget(self._level_db)
        layout.addLayout(level_row)

        transcript_head = QHBoxLayout()
        transcript_title = QLabel("Élő átirat")
        transcript_title.setObjectName("sectionTitle")
        transcript_head.addWidget(transcript_title)
        transcript_head.addStretch(1)
        self._partial_legend = QLabel("Halvány szöveg: ideiglenes")
        self._partial_legend.setStyleSheet("color: #8b96a5; font-size: 11px;")
        transcript_head.addWidget(self._partial_legend)
        layout.addLayout(transcript_head)

        self._transcript = TranscriptView()
        self._transcript.setOpenExternalLinks(False)
        self._transcript.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self._transcript.setPlaceholderText(
            "A felirat itt jelenik meg, miután elindítottad a mikrofont."
        )
        self._transcript.setAccessibleName("Élő magyar átirat")
        self._transcript.setMinimumHeight(240)
        layout.addWidget(self._transcript, 1)

        controls = QHBoxLayout()
        self._start_button = QPushButton("▶  Indítás")
        self._start_button.setObjectName("primary")
        self._start_button.setDefault(True)
        self._start_button.setShortcut("F5")
        self._start_button.clicked.connect(self._start)
        controls.addWidget(self._start_button)
        self._stop_button = QPushButton("■  Leállítás")
        self._stop_button.setShortcut("Esc")
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._stop)
        controls.addWidget(self._stop_button)
        self._clear_button = QPushButton("Törlés")
        self._clear_button.setToolTip("Eltávolítja az aktuálisan látható átiratot")
        self._clear_button.clicked.connect(self._clear_transcript)
        controls.addWidget(self._clear_button)
        controls.addStretch(1)
        self._copy_button = QPushButton("Másolás")
        self._copy_button.clicked.connect(self._copy_transcript)
        controls.addWidget(self._copy_button)
        self._export_button = QPushButton("TXT export…")
        self._export_button.clicked.connect(self._export_transcript)
        controls.addWidget(self._export_button)
        layout.addLayout(controls)

        stats_box = QGroupBox("Élő feldolgozás")
        stats = QGridLayout(stats_box)
        stats.setHorizontalSpacing(18)
        stats.setVerticalSpacing(8)
        self._cpu_value = self._metric(stats, 0, 0, "CPU · aktuális, teljes gép")
        self._ram_value = self._metric(stats, 0, 1, "RAM csúcs · folyamatfa")
        self._rtf_value = self._metric(stats, 0, 2, "RTF · legutóbbi munkamenet")
        self._partial_latency_value = self._metric(stats, 1, 0, "Részleges · p50 / p95 / p99 ms")
        self._final_latency_value = self._metric(stats, 1, 1, "Végleges · p50 / p95 / p99 ms")
        self._queue_value = self._metric(stats, 1, 2, "Frame / STT-sor · most / csúcs")
        self._dropped_value = self._metric(stats, 2, 0, "Eldobott audio frame")
        self._decode_value = self._metric(stats, 2, 1, "Dekódolások · részleges / végleges")
        self._dropped_jobs_value = self._metric(stats, 2, 2, "Eldobott STT-munka")
        for value in (
            self._cpu_value,
            self._ram_value,
            self._rtf_value,
            self._partial_latency_value,
            self._final_latency_value,
        ):
            value.setText("—")
        self._cpu_value.setToolTip(
            "A RoboAssist folyamatfájának használata a teljes logikai gépkapacitás százalékában."
        )
        self._ram_value.setToolTip(
            "A RoboAssist folyamatfájának indulás óta mért legnagyobb working set értéke."
        )
        self._rtf_value.setToolTip(
            "Kumulatív dekódolási idő osztva a munkamenet összes forrás-hangidejével."
        )
        self._metrics_status = QLabel("Folyamatmérés indítása…")
        self._metrics_status.setStyleSheet("color: #697586; font-size: 10px;")
        stats.addWidget(self._metrics_status, 3, 0, 1, 3)
        layout.addWidget(stats_box)

        self._model_help = QLabel()
        self._model_help.setWordWrap(True)
        self._model_help.setStyleSheet("color: #697586; font-size: 11px;")
        layout.addWidget(self._model_help)
        self.setCentralWidget(root)
        self._refresh_actions()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Névjegy – RoboAssist",
            "A RoboAssist az FFmpeg projekt LGPLv2.1 licencű könyvtárait használja.\n\n"
            "A terjesztett Windows csomag FFmpeg forrásarchívuma az "
            "_internal/licenses/upstream-sources mappában, buildreceptjei és "
            "licencszövegei az _internal/licenses/av-runtime mappában találhatók.\n\n"
            "A Qt/PySide forrásarchívumai és licenc-/harmadikfél-közleményei az "
            "_internal/licenses/upstream-sources és _internal/licenses/qt "
            "mappában találhatók. A teljes közleményjegyzék a "
            "THIRD_PARTY_NOTICES.md fájlban van. A bináris csomag licencútja "
            "kiadási ellenőrzés alatt áll.",
        )

    @staticmethod
    def _metric(grid: QGridLayout, row: int, column: int, title: str) -> QLabel:
        cell = QVBoxLayout()
        label = QLabel(title)
        label.setProperty("class", "metric")
        label.setWordWrap(True)
        value = QLabel("0")
        value.setProperty("class", "metricValue")
        value.setWordWrap(True)
        cell.addWidget(label)
        cell.addWidget(value)
        grid.addLayout(cell, row, column)
        return value

    def _load_devices(self) -> None:
        selected = self._device_combo.currentData()
        self._device_combo.clear()
        try:
            self._devices = input_devices()
        except Exception as exc:
            self._devices = []
            self._device_combo.addItem("A mikrofonlista nem olvasható")
            self._device_combo.setEnabled(False)
            self._set_status("error", str(exc) or "Hangbemenet nem érhető el")
            self._refresh_actions()
            return
        self._device_combo.setEnabled(bool(self._devices))
        for device in self._devices:
            suffix = " · alapértelmezett" if device.is_default else ""
            self._device_combo.addItem(
                f"{device.name}  ·  {device.host_api}  ·  "
                f"{device.default_sample_rate:g} Hz{suffix}",
                device.index,
            )
        if not self._devices:
            self._device_combo.addItem("Nem található mikrofon")
        elif selected is not None:
            index = self._device_combo.findData(selected)
            if index >= 0:
                self._device_combo.setCurrentIndex(index)
        self._refresh_actions()

    def _populate_models(self) -> None:
        self._model_combo.clear()
        for label, model_id in self._installed_models:
            self._model_combo.addItem(label, model_id)
        if not self._installed_models:
            self._model_combo.addItem("Nincs helyben telepített modell")
            self._model_combo.setEnabled(False)
            self._model_help.setText(
                "A feliratfeldolgozáshoz előre telepített helyi modell kell. "
                "A RoboAssist futás közben nem tölt le modellt és nem használ "
                "hálózati szolgáltatást. "
                "Telepítési útmutató: models/README.md."
            )
        else:
            self._model_combo.setEnabled(True)
            self._model_help.setText(
                "A hang és az átirat csak a munkamenet memóriájában él. "
                "A TXT export külön, felhasználói művelet. "
                "Leállításkor a munkamenet adatai törlődnek."
            )
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        ready = bool(self._devices and self._installed_models and not self._closing)
        active = self._capture_state in ("loading", "running", "stopping")
        self._start_button.setEnabled(ready and not active)
        self._stop_button.setEnabled(self._capture_state == "running" and not self._closing)
        self._refresh_devices.setEnabled(not active and not self._closing)
        self._device_combo.setEnabled(bool(self._devices) and not active and not self._closing)
        self._model_combo.setEnabled(
            bool(self._installed_models) and not active and not self._closing
        )
        self._language_combo.setEnabled(not active and not self._closing)
        self._always_on_top.setEnabled(not self._closing)
        self._clear_button.setEnabled(not self._buffer.is_empty)
        self._copy_button.setEnabled(not self._buffer.is_empty)
        self._export_button.setEnabled(not self._buffer.is_empty)

    def _start(self) -> None:
        if not self._devices or not self._installed_models:
            return
        item = self._devices[self._device_combo.currentIndex()]
        rate = int(round(item.default_sample_rate))
        self._buffer.begin_session()
        self._pending_presentations.clear()
        self._last_stats = PipelineStats()
        self._partial_latency_samples.clear()
        self._final_latency_samples.clear()
        self._partial_latency_segments.clear()
        self._final_latency_segments.clear()
        self._partial_latency_ids.clear()
        self._final_latency_ids.clear()
        self._accept_events = True
        self._render_transcript()
        self._set_status("loading", "Helyi modell betöltése…")
        self._refresh_actions()
        self.start_requested.emit(
            item.index,
            rate,
            str(self._model_combo.currentData()),
            str(self._language_combo.currentData()),
        )

    def _stop(self) -> None:
        if self._capture_state != "running":
            return
        self._set_status("stopping", "Leállítás és adatok ürítése…")
        self._refresh_actions()
        self.stop_requested.emit()

    def _clear_transcript(self) -> None:
        self._buffer.clear_visible()
        self._pending_presentations.clear()
        self._render_transcript()
        self._refresh_actions()

    def _copy_transcript(self) -> None:
        text = self._buffer.plain_text
        if text:
            QApplication.clipboard().setText(text)

    def _export_transcript(self) -> None:
        text = self._buffer.plain_text
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Átirat mentése", "roboassist-átirat.txt", "Szövegfájl (*.txt)"
        )
        if not path:
            return
        try:
            Path(path).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export hiba", f"Az átirat nem menthető:\n{exc}")

    @Slot(str, str)
    def _on_state_changed(self, state: str, message: str) -> None:
        self._capture_state = state
        self._set_status(state, message)
        if state == "error":
            self._accept_events = False
            self._pending_presentations.clear()
            self._buffer.end_session()
            self._render_transcript()
        elif state == "running":
            self._accept_events = True
        self._refresh_actions()

    @Slot(str)
    def _on_session_started(self, _session_id: str) -> None:
        self._set_status("running", "Mikrofon figyel")

    @Slot(str)
    def _on_session_stopped(self, error: str) -> None:
        self._accept_events = False
        self._pending_presentations.clear()
        self._buffer.end_session()
        self._render_transcript()
        self._set_status("error" if error else "idle", error or "Leállítva · munkamenet törölve")
        self._refresh_actions()

    @Slot()
    def _poll_session(self) -> None:
        events, stats, session_state, session_error = self._controller.snapshot()
        if stats.source_started_monotonic_ns is not None:
            self._last_stats = stats
        if self._stats_callback is not None:
            self._stats_callback(stats)
        changed = False
        if self._accept_events:
            for event in events:
                accepted = self._buffer.accept(event)
                if accepted:
                    self._pending_presentations[event.segment_id] = event
                changed = accepted or changed
        if self._capture_state == "running" and session_state in ("error", "stopped"):
            self._on_state_changed(
                "error",
                session_error or "A mikrofon-munkamenet váratlanul leállt.",
            )
        if changed:
            self._render_transcript()
            self._refresh_actions()
        self._render_stats(
            stats if stats.source_started_monotonic_ns is not None else self._last_stats
        )
        self._render_process_metrics()

    @Slot(object)
    def _on_transcript_painted(self, displayed_monotonic_ns: int) -> None:
        """Record only the newest revision that is still visible after painting."""
        if not self._pending_presentations:
            return
        pending, self._pending_presentations = self._pending_presentations, {}
        for segment_id, event in pending.items():
            if self._buffer.current_revision(segment_id) == event.revision:
                self._record_live_latency(event, displayed_monotonic_ns)
                if self._presentation_callback is not None:
                    self._presentation_callback(event, displayed_monotonic_ns)

    def _record_live_latency(self, event: TranscriptEvent, displayed_monotonic_ns: int) -> None:
        source_start_ns = self._last_stats.source_started_monotonic_ns
        if source_start_ns is None:
            return
        if event.type == "partial":
            seen = self._partial_latency_ids
            order = self._partial_latency_segments
            samples = self._partial_latency_samples
            audio_time_ms = event.audio_start_ms
        else:
            seen = self._final_latency_ids
            order = self._final_latency_segments
            samples = self._final_latency_samples
            audio_time_ms = event.audio_end_ms
        if event.segment_id in seen:
            return
        if len(order) == order.maxlen:
            seen.discard(order[0])
        order.append(event.segment_id)
        seen.add(event.segment_id)
        latency_ms = (displayed_monotonic_ns - source_start_ns) / 1_000_000 - audio_time_ms
        if math.isfinite(latency_ms):
            samples.append(latency_ms)
        self._render_latency_metrics()

    def _render_latency_metrics(self) -> None:
        for label, samples in (
            (self._partial_latency_value, self._partial_latency_samples),
            (self._final_latency_value, self._final_latency_samples),
        ):
            distribution = percentile_summary(tuple(samples))
            if distribution.count == 0:
                label.setText("—")
            else:
                label.setText(
                    f"{distribution.p50:.0f} / {distribution.p95:.0f} / {distribution.p99:.0f}"
                )

    def _render_transcript(self) -> None:
        self._transcript.render_buffer(self._buffer)
        self._refresh_actions()

    def _render_stats(self, stats: PipelineStats) -> None:
        dbfs = max(-60.0, min(0.0, stats.input_level_dbfs))
        self._level_bar.setValue(int((dbfs + 60.0) / 60.0 * 100))
        self._level_db.setText("−∞ dBFS" if dbfs <= -59.9 else f"{dbfs:.0f} dBFS")
        self._queue_value.setText(
            f"Frame {stats.frame_backlog}/{stats.max_frame_backlog} · "
            f"STT {stats.job_backlog}/{stats.max_job_backlog}"
        )
        self._dropped_value.setText(str(stats.dropped_frames))
        self._decode_value.setText(f"{stats.partial_decodes} / {stats.final_decodes}")
        self._dropped_jobs_value.setText(
            str(stats.partial_jobs_dropped + stats.final_jobs_rejected)
        )
        try:
            rtf = summarize_pipeline(stats).rtf
        except ValueError:
            rtf = None
        self._rtf_value.setText("—" if rtf is None else f"{rtf:.2f}")
        self._render_latency_metrics()
        if self._capture_state == "running":
            if stats.decoder_busy or stats.job_backlog:
                self._set_status("processing", "Beszéd feldolgozása")
            elif self._status_label.text() != "Mikrofon figyel":
                self._set_status("running", "Mikrofon figyel")

    @Slot(object, object)
    def _on_process_metrics_sample(
        self, sample: ProcessUsageSample, summary: ProcessUsageSummary
    ) -> None:
        self._process_metrics_sample = sample
        self._process_metrics_summary = summary
        self._process_metrics_error = None
        self._render_process_metrics()

    @Slot(str)
    def _on_process_metrics_error(self, error_type: str) -> None:
        self._process_metrics_sample = None
        self._process_metrics_summary = None
        self._process_metrics_error = error_type
        self._render_process_metrics()

    def _render_process_metrics(self) -> None:
        sample = self._process_metrics_sample
        summary = self._process_metrics_summary
        if self._process_metrics_error is not None:
            self._clear_process_metrics()
            self._metrics_status.setText(
                f"Folyamatmérés nem érhető el ({self._process_metrics_error})"
            )
            return
        if sample is None or summary is None:
            self._clear_process_metrics()
            self._metrics_status.setText("Folyamatmérés indítása…")
            return
        age_ns = time.monotonic_ns() - sample.monotonic_ns
        if age_ns < 0 or age_ns > 2_500_000_000:
            self._clear_process_metrics()
            self._metrics_status.setText("Elavult folyamatmérés · új adat nem érhető el")
            return
        cpu = sample.cpu_percent
        self._cpu_value.setText("—" if cpu is None else f"{cpu:.1f}%")
        memory = summary.peak_working_set_bytes
        self._ram_value.setText("—" if memory is None else f"{memory / 1_048_576:.0f} MB")
        self._metrics_status.setText(
            f"Friss · {sample.process_count} folyamat · {age_ns / 1_000_000_000:.1f} s"
        )

    def _clear_process_metrics(self) -> None:
        self._cpu_value.setText("—")
        self._ram_value.setText("—")

    def _set_status(self, state: str, message: str) -> None:
        colors = {
            "idle": "#94a3b8",
            "loading": "#f4b740",
            "running": "#32c48d",
            "processing": "#5ca5ff",
            "stopping": "#f4b740",
            "error": "#ff7373",
        }
        self._status_dot.setStyleSheet(f"color:{colors.get(state, '#94a3b8')};font-size:18px;")
        self._status_label.setText(message)

    def _set_always_on_top(self, enabled: bool) -> None:
        self._settings.setValue("always_on_top", enabled)
        flags = self.windowFlags()
        flag = Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags | flag if enabled else flags & ~flag)
        self.show()

    @property
    def _settings(self) -> QSettings:
        return QSettings("RoboAssist", "OfflineSTT")

    def _restore_settings(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            self._process_metrics_thread.requestInterruption()
            if self._process_metrics_thread.isRunning():
                self._process_metrics_thread.wait(2000)
            self._settings.setValue("geometry", self.saveGeometry())
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        self._closing = True
        self._set_status("stopping", "A munkamenet lezárása…")
        self._refresh_actions()
        self.close_requested.emit()

    @Slot()
    def _on_controller_closed(self) -> None:
        self._accept_events = False
        self._buffer.end_session()
        self._thread.quit()
        self._thread.wait(6500)
        self._allow_close = True
        self.close()
