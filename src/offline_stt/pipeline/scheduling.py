"""Bounded queues. No queue capacity wait on the capture or VAD path."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from queue import Empty, Full, Queue
from threading import Condition, Event, Lock

from offline_stt.audio.types import AudioFrame
from offline_stt.pipeline.types import PipelineError, PipelineStats


class Counters:
    def __init__(self) -> None:
        self._values = asdict(PipelineStats())
        self._lock = Lock()

    def add(self, name: str, value: int | float = 1) -> None:
        with self._lock:
            self._values[name] += value

    def backlog(self, kind: str, count: int) -> None:
        with self._lock:
            self._values[kind + "_backlog"] = count
            key = "max_" + kind + "_backlog"
            self._values[key] = max(self._values[key], count)

    def snapshot(self) -> PipelineStats:
        with self._lock:
            return PipelineStats(**self._values)


class FrameQueue:
    def __init__(self, capacity: int, counters: Counters) -> None:
        self._queue: Queue[AudioFrame] = Queue(capacity)
        self.counters = counters

    def put(self, frame: AudioFrame) -> None:
        if len(frame.samples) > 480:
            raise PipelineError("Source frame exceeds the 30 ms input bound")
        try:
            self._queue.put_nowait(frame)
        except Full as exc:
            self.counters.add("dropped_frames")
            self.counters.add("dropped_samples", len(frame.samples))
            raise PipelineError(
                "Audio frame queue overflow; session audio is discontinuous"
            ) from exc
        self.counters.add("audio_frames")
        self.counters.add("audio_samples", len(frame.samples))
        self.counters.backlog("frame", self._queue.qsize())

    def get(self) -> AudioFrame | None:
        try:
            frame = self._queue.get(timeout=0.02)
        except Empty:
            return None
        self.counters.backlog("frame", self._queue.qsize())
        return frame

    def next(self, producer_done: Event) -> tuple[AudioFrame | None, bool]:
        frame = self.get()
        if frame is not None or not producer_done.is_set():
            return frame, False
        # Done guarantees no future puts. A last put can race with the first Empty.
        frame = self.get()
        return frame, frame is None


@dataclass(frozen=True)
class DecodeJob:
    segment: int
    segment_start: int
    frame: AudioFrame
    final: bool
    sequence: int = 0


class JobQueue:
    """FIFO finals have priority; at most one pending replaceable partial."""

    def __init__(self, capacity: int, counters: Counters) -> None:
        self.capacity = capacity
        self.counters = counters
        self._finals: deque[DecodeJob] = deque()
        self._partial: DecodeJob | None = None
        self._condition = Condition()
        self._sequence = 0
        self._last_final = 0
        self.finished = False
        self.aborted = False

    def _backlog(self) -> None:
        self.counters.backlog("job", len(self._finals) + (self._partial is not None))

    def put(self, job: DecodeJob) -> None:
        from dataclasses import replace

        with self._condition:
            if self.finished or self.aborted:
                raise PipelineError("Work queue is closed")
            self._sequence += 1
            job = replace(job, sequence=self._sequence)
            if job.final:
                if len(self._finals) >= self.capacity:
                    self.counters.add("final_jobs_rejected")
                    raise PipelineError("Final queue overflow; no final may be silently discarded")
                self._last_final = job.segment
                self._finals.append(job)
                if self._partial is not None and self._partial.segment <= job.segment:
                    self._partial = None
                    self.counters.add("partial_jobs_dropped")
            else:
                if self._partial is not None:
                    self.counters.add("partial_jobs_dropped")
                self._partial = job
            self._backlog()
            self._condition.notify_all()

    def get(self) -> DecodeJob | None:
        with self._condition:
            while not self.aborted and not self._finals and self._partial is None:
                if self.finished:
                    return None
                self._condition.wait(0.05)
            if self.aborted:
                return None
            if self._finals:
                job = self._finals.popleft()
            else:
                assert self._partial is not None
                job, self._partial = self._partial, None
            self._backlog()
            return job

    def stale(self, job: DecodeJob) -> bool:
        with self._condition:
            return self.aborted or (
                not job.final and (job.segment <= self._last_final or job.sequence < self._sequence)
            )

    def finish(self, *, abort: bool = False) -> None:
        with self._condition:
            self.finished = True
            self.aborted = abort
            if abort:
                self._finals.clear()
                self._partial = None
                self._backlog()
            self._condition.notify_all()
