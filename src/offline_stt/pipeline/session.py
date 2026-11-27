"""UI-independent session owner with a killable Windows-spawn worker process."""

from __future__ import annotations

import math
import multiprocessing as mp
import pickle
import time
import uuid
from collections import deque
from dataclasses import dataclass, replace
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from multiprocessing.synchronize import Event as ProcessEvent
from threading import Event, RLock, Thread
from typing import TYPE_CHECKING, cast

from offline_stt.audio.replay import WavReplaySource
from offline_stt.config import Config
from offline_stt.engines import FasterWhisperEngine, LocalModelStore
from offline_stt.pipeline.types import (
    PipelineError,
    PipelineStats,
    SessionState,
    TranscriptEvent,
)
from offline_stt.worker_bootstrap import run_session_bootstrap

if TYPE_CHECKING:
    from offline_stt.pipeline.worker import EngineFactory, SourceFactory


@dataclass(frozen=True)
class LocalEngineFactory:
    config: Config
    catalog: str
    root: str

    def __call__(self) -> FasterWhisperEngine:
        return FasterWhisperEngine.from_config(
            self.config, LocalModelStore(self.catalog, self.root)
        )


@dataclass(frozen=True)
class WavSourceFactory:
    path: str
    frame_ms: int = 20

    def __call__(self) -> WavReplaySource:
        return WavReplaySource(self.path, frame_ms=self.frame_ms)


class Session:
    """Lifecycle calls are serialized by the owner; drain_events/stats are thread-safe.

    Factories must be spawn-picklable, defined in importable modules, and create
    resources only when called. Never pass a live capture stream or decoder.
    """

    def __init__(
        self, config: Config, source_factory: SourceFactory, engine_factory: EngineFactory
    ) -> None:
        self.config = config
        self.source_factory = source_factory
        self.engine_factory = engine_factory
        self.state = SessionState.IDLE
        self.error: str | None = None
        self.session_id = ""
        self._process: BaseProcess | None = None
        self._stop: ProcessEvent | None = None
        self._connection: Connection | None = None
        self._collector: Thread | None = None
        self._ready = Event()
        self._lock = RLock()
        self._events: deque[TranscriptEvent] = deque()
        self._stats = PipelineStats()
        self._partial_dropped = self._final_failures = self._forced = 0

    @property
    def worker_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def _fail(self, message: str) -> None:
        with self._lock:
            if self.error is None:
                self.error = message
            self.state = SessionState.ERROR
            self._events.clear()
            if self._stop is not None:
                self._stop.set()
            self._ready.set()

    def _event(self, event: TranscriptEvent) -> None:
        if event.session_id != self.session_id or self.error is not None:
            return
        # A final replaces its pending partial; repeated partials are coalesced.
        older = [
            e for e in self._events if e.type == "partial" and e.segment_id == event.segment_id
        ]
        for old in older:
            self._events.remove(old)
            self._partial_dropped += 1
        if len(self._events) >= self.config.pipeline.event_queue_capacity:
            disposable = next((e for e in self._events if e.type == "partial"), None)
            if disposable is not None:
                self._events.remove(disposable)
                self._partial_dropped += 1
            elif event.type == "partial":
                self._partial_dropped += 1
                return
            else:
                self._final_failures += 1
                self._fail("Transcript event buffer overflow; final delivery failed")
                return
        self._events.append(event)

    def _collect(self, connection: Connection, session_id: str) -> None:
        completed = False
        try:
            while True:
                kind, value = connection.recv()
                with self._lock:
                    if session_id != self.session_id:
                        break
                    if kind == "ready":
                        if self.error is None:
                            self.state = SessionState.RUNNING
                        self._ready.set()
                    elif kind == "error":
                        self._fail(str(value))
                    elif kind == "stats":
                        self._stats = value
                    elif kind == "event":
                        self._event(value)
                    elif kind == "done":
                        completed = True
                        break
        except (EOFError, OSError):
            pass
        finally:
            with self._lock:
                if session_id == self.session_id:
                    if not completed and self.error is None:
                        self._fail("Session process ended without a clean completion")
                    elif self.error is None:
                        self.state = SessionState.STOPPED
                    self._ready.set()
            connection.close()

    def _release(self) -> None:
        if self.worker_alive:
            raise PipelineError("Cannot release a live session worker")
        if self._collector is not None:
            self._collector.join(0.2)
            if self._collector.is_alive():
                raise PipelineError("Event collector did not finish")
            self._collector = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._process is not None:
            self._process.close()
            self._process = None
        self._stop = None

    def start(self, *, timeout: float = 30) -> str:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Startup timeout must be finite and positive")
        if self.state == SessionState.CLOSED or self.worker_alive:
            raise PipelineError("Cannot start a closed/running session")
        self._release()
        with self._lock:
            self.error = None
            self._events.clear()
            self._stats = PipelineStats()
            self._partial_dropped = self._final_failures = self._forced = 0
            self.session_id = uuid.uuid4().hex
            self.state = SessionState.STARTING
            self._ready.clear()
        context = mp.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        self._stop = context.Event()
        self._connection = cast(Connection, receiver)
        try:
            payload = pickle.dumps(
                (self.session_id, self.config, self.source_factory, self.engine_factory),
                protocol=pickle.HIGHEST_PROTOCOL,
            )
            self._process = context.Process(
                target=run_session_bootstrap,
                args=(payload, self._stop, sender),
                name="RoboAssist session",
            )
            self._process.start()
        except Exception as exc:
            sender.close()
            receiver.close()
            self._process = None
            self._fail(f"Session spawn failed: {exc}")
            raise PipelineError(self.error) from exc
        sender.close()
        self._collector = Thread(
            target=self._collect, args=(receiver, self.session_id), name="STT events", daemon=True
        )
        self._collector.start()
        if not self._ready.wait(timeout):
            self._fail("Session startup timeout")
            self.stop()
            raise PipelineError(self.error)
        if self.error is not None:
            self.stop()
            raise PipelineError(self.error)
        return self.session_id

    def wait(self, timeout: float = 0) -> bool:
        """Wait for EOF without requesting Stop; False leaves the session running."""
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Wait timeout must be finite and nonnegative")
        if self._process is None:
            return True
        self._process.join(timeout)
        if self.worker_alive:
            return False
        if self._collector is not None:
            self._collector.join(0.2)
        return True

    def stop(self, *, timeout: float | None = None) -> None:
        """Drain accepted frames and flush once; deadline forces process termination."""
        budget = self.config.pipeline.stop_timeout_ms / 1000 if timeout is None else timeout
        if not math.isfinite(budget) or not 1 <= budget <= 60:
            raise ValueError("Stop timeout must be 1..60 seconds")
        if self._process is None:
            return
        deadline = time.monotonic() + budget
        if self._stop is not None:
            self._stop.set()
        self._process.join(max(0, budget - 0.35))
        forced = self.worker_alive
        if forced:
            self._forced += 1
            self._fail("Stop/flush timeout; unfinished audio discarded, worker terminated")
            self._process.terminate()
            self._process.join(0.15)
            if self.worker_alive:
                self._process.kill()
                self._process.join(max(0, deadline - time.monotonic()))
        if self.worker_alive:
            raise PipelineError("OS did not terminate the session process within the deadline")
        if self._collector is not None:
            self._collector.join(max(0, deadline - time.monotonic()))
        if forced:
            raise PipelineError(self.error)

    def drain_events(self) -> tuple[TranscriptEvent, ...]:
        with self._lock:
            result = tuple(self._events)
            self._events.clear()
            return result

    @property
    def stats(self) -> PipelineStats:
        with self._lock:
            return replace(
                self._stats,
                forced_terminations=self._forced,
                output_partial_dropped=self._partial_dropped,
                output_final_failures=self._final_failures,
            )

    def reset(self) -> None:
        if self.state == SessionState.CLOSED:
            raise PipelineError("Closed session cannot be reset")
        try:
            self.stop()
        finally:
            self._release()
            with self._lock:
                self._events.clear()
                self.session_id = ""
                self.error = None
                self.state = SessionState.IDLE

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._release()
            with self._lock:
                self._events.clear()
                self.state = SessionState.CLOSED
