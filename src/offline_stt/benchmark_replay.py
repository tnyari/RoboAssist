"""Run one local, real-time WAV replay against annotations and the Qt transcript view."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from offline_stt.benchmark_report import (
    BenchmarkMetrics,
    BenchmarkReport,
    RunMetadata,
    TranscriptRow,
    export_report,
)
from offline_stt.config import ApplicationConfig, Config, EngineConfig
from offline_stt.engines import (
    EngineOptions,
    FasterWhisperEngine,
    LocalModelStore,
)
from offline_stt.metrics import (
    CriticalKind,
    EventPresentation,
    UtteranceAnnotation,
    evaluate_annotations,
    summarize_pipeline,
)
from offline_stt.pipeline.session import Session, WavSourceFactory
from offline_stt.pipeline.types import PipelineStats, SessionState, TranscriptEvent
from offline_stt.system_metrics import ProcessTreeSampler
from offline_stt.ui.transcript import TranscriptBuffer
from offline_stt.ui.window import TranscriptView

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_CRITICAL_KINDS = {"text", "integer", "decimal", "identifier"}


@dataclass(frozen=True)
class ReplayEngineFactory:
    catalog_path: str
    model_root: str
    model_id: str
    language: str
    cpu_threads: int
    max_audio_seconds: float

    def __call__(self) -> FasterWhisperEngine:
        return FasterWhisperEngine(
            LocalModelStore(self.catalog_path, self.model_root),
            self.model_id,
            options=EngineOptions(
                language=self.language,
                cpu_threads=self.cpu_threads,
                max_audio_seconds=self.max_audio_seconds,
            ),
        )


def load_annotations(path: str | Path) -> tuple[UtteranceAnnotation, ...]:
    """Read local JSONL annotations without logging or persisting transcript text."""
    annotations: list[UtteranceAnnotation] = []
    expected_keys = {
        "utterance_id",
        "speech_start_ms",
        "speech_end_ms",
        "reference_text",
        "critical_fields",
    }
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Annotation line {line_number} is invalid JSON") from exc
        if not isinstance(value, dict) or set(value) != expected_keys:
            raise ValueError(f"Annotation line {line_number} has an unexpected schema")
        fields_value = value["critical_fields"]
        if not isinstance(fields_value, dict):
            raise ValueError(f"Annotation line {line_number} critical_fields must be an object")
        fields: dict[str, tuple[str, CriticalKind]] = {}
        for name, field_value in fields_value.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or not isinstance(field_value, dict)
                or set(field_value) != {"value", "kind"}
                or not isinstance(field_value["value"], str)
                or not isinstance(field_value["kind"], str)
                or field_value["kind"] not in _CRITICAL_KINDS
                or not field_value["value"].strip()
            ):
                raise ValueError(f"Annotation line {line_number} has an invalid critical field")
            fields[name] = (field_value["value"], cast(CriticalKind, field_value["kind"]))
        start = value["speech_start_ms"]
        end = value["speech_end_ms"]
        if (
            not isinstance(value["utterance_id"], str)
            or not value["utterance_id"].strip()
            or not isinstance(value["reference_text"], str)
            or not value["reference_text"].strip()
            or type(start) not in (int, float)
            or type(end) not in (int, float)
        ):
            raise ValueError(f"Annotation line {line_number} has invalid field types")
        if not math.isfinite(float(start)) or not math.isfinite(float(end)):
            raise ValueError(f"Annotation line {line_number} has non-finite speech bounds")
        if start < 0 or end <= start:
            raise ValueError(f"Annotation line {line_number} has invalid speech bounds")
        annotations.append(
            UtteranceAnnotation(
                value["utterance_id"],
                float(start),
                float(end),
                value["reference_text"],
                fields,
            )
        )
    if not annotations:
        raise ValueError("At least one utterance annotation is required")
    if len({item.utterance_id for item in annotations}) != len(annotations):
        raise ValueError("Utterance annotation IDs must be unique")
    return tuple(annotations)


class ReplayBenchmarkWindow(QMainWindow):
    """Display the shared transcript widget and collect run data in memory."""

    def __init__(
        self,
        session: Session,
        annotations: tuple[UtteranceAnnotation, ...],
        metadata: RunMetadata,
        output_parent: Path,
        *,
        include_transcript: bool,
        sampler: ProcessTreeSampler,
    ) -> None:
        super().__init__()
        self._session = session
        self._annotations = annotations
        self._metadata = metadata
        self._output_parent = output_parent
        self._include_transcript = include_transcript
        self._sampler = sampler
        self._buffer = TranscriptBuffer()
        self._presentations: list[EventPresentation] = []
        self._pending: dict[str, TranscriptEvent] = {}
        self._stats = PipelineStats()
        self._finishing = False
        self._finished = False
        self._cancelled = False
        self.error: str | None = None
        self.report_path: Path | None = None

        self.setWindowTitle("RoboAssist · helyi replay benchmark")
        self.setMinimumSize(680, 560)
        self.resize(940, 720)
        self.setStyleSheet(
            "QMainWindow { background: #f4f6fa; } "
            "QTextBrowser { border: 1px solid #dce2eb; border-radius: 10px; "
            "background: #ffffff; color: #172438; padding: 16px; }"
        )
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(13)
        self._status = QLabel("Helyi modell indítása és replay előkészítése…")
        self._status.setStyleSheet("color: #172438; font-size: 14px; font-weight: 600;")
        self._transcript = TranscriptView()
        self._transcript.setOpenExternalLinks(False)
        self._transcript.setReadOnly(True)
        layout.addWidget(self._status)
        layout.addWidget(self._transcript, 1)
        self.setCentralWidget(root)
        self._transcript.painted.connect(self._on_painted)

        self._poller = QTimer(self)
        self._poller.setInterval(100)
        self._poller.timeout.connect(self._poll)
        self._process_poller = QTimer(self)
        self._process_poller.setInterval(1000)
        self._process_poller.timeout.connect(self._sample_processes)

    def start_replay(self, *, startup_timeout: float) -> None:
        self.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        self._session.start(timeout=startup_timeout)
        self._stats = self._session.stats
        self._sampler.sample()
        self._status.setText("Időzített helyi WAV replay fut…")
        self._poller.start()
        self._process_poller.start()

    def _poll(self) -> None:
        events = self._session.drain_events()
        changed = False
        for event in events:
            accepted = self._buffer.accept(event)
            if accepted:
                self._pending[event.segment_id] = event
            changed = accepted or changed
        self._stats = self._session.stats
        if changed:
            self._transcript.render_buffer(self._buffer)
        if self._session.state == SessionState.ERROR:
            self._fail(self._session.error or "Replay munkamenet-hiba")
        elif self._session.state == SessionState.STOPPED and self._session.wait(0):
            self._finishing = True
            if not self._pending:
                self._complete()

    def _sample_processes(self) -> None:
        try:
            self._sampler.sample()
        except (OSError, RuntimeError, ValueError) as exc:
            self._fail(f"A processzfa-mérés nem teljes: {type(exc).__name__}")

    def _on_painted(self, displayed_monotonic_ns: int) -> None:
        if not self._pending:
            return
        pending, self._pending = self._pending, {}
        for segment_id, event in pending.items():
            if self._buffer.current_revision(segment_id) == event.revision:
                self._presentations.append(EventPresentation(event, displayed_monotonic_ns))
        if self._finishing:
            self._complete()

    def _fail(self, message: str) -> None:
        if self._finished:
            return
        self.error = message
        self._finished = True
        self._poller.stop()
        self._process_poller.stop()
        self._status.setText(f"Hiba: {message}")
        try:
            self._session.close()
        except Exception as exc:
            self.error = f"{message}; session cleanup failed ({type(exc).__name__})"
            self._status.setText(f"Hiba: {self.error}")
        finally:
            self._quit_application(0)

    def _complete(self) -> None:
        if self._finished:
            return
        self._poller.stop()
        self._process_poller.stop()
        try:
            self._sampler.sample()
            self._stats = self._session.stats
            if self._stats.source_started_monotonic_ns is None:
                raise RuntimeError("A forrás monotonic kezdőideje hiányzik")
            evaluation = evaluate_annotations(
                self._annotations,
                self._presentations,
                source_started_monotonic_ns=self._stats.source_started_monotonic_ns,
            )
            system = self._sampler.summary
            metrics = BenchmarkMetrics(
                pipeline=summarize_pipeline(self._stats),
                first_partial_latency_ms=evaluation.first_partial_latency_ms,
                first_final_latency_ms=evaluation.first_final_latency_ms,
                vad_endpoint_latency_ms=evaluation.vad_endpoint_latency_ms,
                wer=evaluation.wer,
                cer=evaluation.cer,
                critical_fields=evaluation.critical_fields,
                average_cpu_percent=system.average_cpu_percent,
                peak_working_set_bytes=system.peak_working_set_bytes,
                process_sample_count=system.process_sample_count,
            )
            report = BenchmarkReport(
                self._metadata,
                metrics,
                tuple(
                    TranscriptRow(item.utterance_id, item.reference_text, item.hypothesis_text)
                    for item in evaluation.utterances
                ),
            )
            self.report_path = export_report(
                report,
                self._output_parent,
                include_transcript=self._include_transcript,
            )
            self._status.setText("Replay kész · riport mentve")
            self._finished = True
        except (OSError, RuntimeError, ValueError) as exc:
            self.error = str(exc) or type(exc).__name__
            self._status.setText(f"Hiba: {self.error}")
            self._finished = True
        finally:
            try:
                self._session.close()
            except Exception as exc:
                detail = f"Session cleanup failed ({type(exc).__name__})"
                self.error = f"{self.error}; {detail}" if self.error else detail
                self._status.setText(f"Hiba: {self.error}")
                self._finished = True
            finally:
                self._quit_application(250)

    @staticmethod
    def _quit_application(delay_ms: int) -> None:
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(delay_ms, app.quit)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._finished:
            self._cancelled = True
            self._poller.stop()
            self._process_poller.stop()
            try:
                self._session.close()
            except Exception as exc:
                self.error = f"Session cleanup failed ({type(exc).__name__})"
        event.accept()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Helyi, időzített WAV replay; hangfelvétel és hálózati modellletöltés nélkül"
    )
    parser.add_argument("--wav", required=True, type=Path, help="Helyi PCM WAV fájl")
    parser.add_argument("--annotations", required=True, type=Path, help="Helyi annotációs JSONL")
    parser.add_argument("--catalog", type=Path, help="Helyi models/manifest.json")
    parser.add_argument("--model-root", type=Path, help="Helyi hash-ellenőrzött modellkönyvtár")
    parser.add_argument("--model", default="base-multilingual")
    parser.add_argument("--language", default="hu")
    parser.add_argument("--threads", required=True, type=int, choices=(2, 4, 8))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--hardware-category", required=True)
    parser.add_argument("--output-parent", required=True, type=Path)
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument(
        "--include-transcript",
        action="store_true",
        help="A referencia és felismert szöveg külön transcripts.jsonl fájlba kerül",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if sys.platform != "win32":
        print("A benchmark runner csak Windows alatt támogatott.", file=sys.stderr)
        return 2
    if _RUN_ID.fullmatch(args.run_id) is None:
        print("A run-id csak egyszerű azonosító lehet.", file=sys.stderr)
        return 2
    if not args.test_id.strip() or not args.hardware_category.strip():
        print("A test-id és hardware-category nem lehet üres.", file=sys.stderr)
        return 2
    if not math.isfinite(args.startup_timeout) or args.startup_timeout <= 0:
        print("A startup-timeout pozitív érték legyen.", file=sys.stderr)
        return 2
    if not args.wav.is_file() or not args.annotations.is_file():
        print("A WAV és annotációs fájl helyi, létező fájl legyen.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = args.catalog or repo_root / "models" / "manifest.json"
    default_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    default_root /= Path("RoboAssist") / "OfflineSTT" / "models" / "cache"
    model_root = args.model_root or default_root
    destination = args.output_parent / args.run_id
    if destination.exists():
        print("A run-id könyvtár már létezik; a meglévő riport nem írható felül.", file=sys.stderr)
        return 2
    try:
        annotations = load_annotations(args.annotations)
        verified = LocalModelStore(catalog_path, model_root).verify(args.model)
    except (OSError, ValueError, RuntimeError) as exc:
        print(
            f"A helyi benchmark bemenet nem ellenőrizhető ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    model_file = next((item for item in verified.spec.files if item.name == "model.bin"), None)
    if model_file is None:
        print("A modell-manifest nem tartalmaz model.bin fájlt.", file=sys.stderr)
        return 2
    cpu_model = platform.processor() or platform.machine()
    logical_cpus = os.cpu_count() or 1
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    config = Config(
        application=ApplicationConfig(language=args.language, offline=True, telemetry=False),
        engine=EngineConfig(model=args.model),
    )
    engine_factory = ReplayEngineFactory(
        str(catalog_path),
        str(model_root),
        args.model,
        args.language,
        args.threads,
        config.vad.max_segment_ms / 1000,
    )
    session = Session(
        config,
        WavSourceFactory(str(args.wav), frame_ms=20),
        engine_factory,
    )
    metadata = RunMetadata(
        run_id=args.run_id,
        test_id=args.test_id,
        hardware_category=args.hardware_category,
        model_id=args.model,
        model_revision=verified.spec.revision,
        model_sha256=model_file.sha256,
        app_version=str(project["version"]),
        operating_system=platform.platform(),
        cpu_model=cpu_model,
        logical_cpu_count=logical_cpus,
        cpu_threads=args.threads,
        language=args.language,
        started_utc=datetime.now(UTC).isoformat(),
        parameters={
            "sample_rate_hz": 16_000,
            "frame_ms": 20,
            "source": "local_pcm_wav_realtime_replay",
            "cpu_normalization": "full_machine_logical_processors",
            "model_load_included_in_cpu": True,
            "hardware_category_source": "operator_supplied",
        },
    )

    app = QApplication(sys.argv[:1] if argv is None else [sys.argv[0], *argv])
    app.setOrganizationName("RoboAssist")
    app.setApplicationName("OfflineSTTBenchmark")
    try:
        window = ReplayBenchmarkWindow(
            session,
            annotations,
            metadata,
            args.output_parent,
            include_transcript=args.include_transcript,
            sampler=ProcessTreeSampler(logical_cpu_count=logical_cpus),
        )
        window.show()
        app.processEvents()
        try:
            window.start_replay(startup_timeout=args.startup_timeout)
        except Exception as exc:
            try:
                session.close()
            except Exception as close_exc:
                print(
                    f"A munkamenet lezárása nem sikerült ({type(close_exc).__name__}).",
                    file=sys.stderr,
                )
            print(f"A replay munkamenet nem indítható ({type(exc).__name__}).", file=sys.stderr)
            return 2
        app.exec()
        if window._cancelled:
            print("A replay futást megszakították; riport nem készült.", file=sys.stderr)
            return 2
        if window.error or window.report_path is None:
            print(
                f"A replay benchmark hibával leállt: {window.error or 'nincs riport'}",
                file=sys.stderr,
            )
            return 2
        print(
            json.dumps(
                {"status": "passed", "run_id": args.run_id, "report_dir": str(window.report_path)}
            )
        )
        return 0
    finally:
        if session.state != SessionState.CLOSED:
            try:
                session.close()
            except Exception as exc:
                print(
                    f"A munkamenet lezárása nem sikerült ({type(exc).__name__}).",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
