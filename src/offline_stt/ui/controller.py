"""Background lifecycle controller for the Qt interface."""

from __future__ import annotations

from dataclasses import replace
from threading import Lock

from PySide6.QtCore import QObject, Signal, Slot

from offline_stt.audio.microphone import MicrophoneSource
from offline_stt.config import Config
from offline_stt.pipeline.session import LocalEngineFactory, Session
from offline_stt.pipeline.types import PipelineStats, TranscriptEvent


class MicrophoneSourceFactory:
    """Spawn-picklable factory; the capture stream is created in the worker process."""

    def __init__(self, device: int, sample_rate: int, frame_ms: int) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms

    def __call__(self) -> MicrophoneSource:
        return MicrophoneSource(
            self.device, sample_rate=self.sample_rate, channels=1, frame_ms=self.frame_ms
        )


class SessionController(QObject):
    """Owns session lifecycle on a QThread; snapshots remain safe to poll from the UI."""

    state_changed = Signal(str, str)
    session_started = Signal(str)
    session_stopped = Signal(str)
    closed = Signal()

    def __init__(
        self,
        config: Config,
        catalog_path: str,
        model_root: str,
    ) -> None:
        super().__init__()
        self._config = config
        self._catalog_path = catalog_path
        self._model_root = model_root
        self._session: Session | None = None
        self._session_lock = Lock()

    @Slot(int, int, str, str)
    def start(self, device: int, sample_rate: int, model: str, language: str) -> None:
        self.state_changed.emit("loading", "Helyi modell betöltése…")
        with self._session_lock:
            previous = self._session
        if previous is not None:
            try:
                previous.close()
            except Exception as exc:
                self.state_changed.emit(
                    "error", str(exc) or "Az előző munkamenet erőforrásai nem zárhatók le."
                )
                return
        config = replace(
            self._config,
            application=replace(self._config.application, language=language),
            engine=replace(self._config.engine, model=model),
        )
        session = Session(
            config,
            MicrophoneSourceFactory(device, sample_rate, config.audio.frame_ms),
            LocalEngineFactory(config, self._catalog_path, self._model_root),
        )
        with self._session_lock:
            self._session = session
        try:
            session_id = session.start()
        except Exception as exc:
            message = str(exc) or "A mikrofonos munkamenet nem indítható el."
            try:
                session.close()
            except Exception:
                pass
            with self._session_lock:
                if self._session is session:
                    self._session = None
            self.state_changed.emit("error", message)
            return
        self.session_started.emit(session_id)
        self.state_changed.emit("running", "Mikrofon figyel")

    @Slot()
    def stop(self) -> None:
        with self._session_lock:
            session = self._session
        if session is None:
            self.session_stopped.emit("")
            return
        self.state_changed.emit("stopping", "Leállítás és adatok ürítése…")
        error = ""
        try:
            session.stop()
        except Exception as exc:
            error = str(exc) or "A munkamenet leállítása hibát jelzett."
        finally:
            try:
                session.close()
            except Exception as exc:
                error = error or str(exc) or "A munkamenet erőforrásai nem zárhatók le."
            with self._session_lock:
                if self._session is session:
                    self._session = None
        self.state_changed.emit("error" if error else "idle", error or "Leállítva")
        self.session_stopped.emit(error)

    @Slot()
    def close_session(self) -> None:
        with self._session_lock:
            session = self._session
        try:
            if session is not None:
                session.close()
        except Exception as exc:
            self.state_changed.emit("error", str(exc) or "Leállítási hiba")
        finally:
            with self._session_lock:
                if self._session is session:
                    self._session = None
            self.closed.emit()

    def snapshot(self) -> tuple[tuple[TranscriptEvent, ...], PipelineStats, str, str | None]:
        """Drain only the session's lock-protected output; never decode on the UI thread."""
        with self._session_lock:
            session = self._session
        if session is None:
            return (), PipelineStats(), "idle", None
        return session.drain_events(), session.stats, session.state.value, session.error
