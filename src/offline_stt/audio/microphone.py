"""Explicit PortAudio capture with a preallocated single-producer/single-reader ring."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol, cast

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]

from offline_stt.audio.normalize import AudioNormalizer
from offline_stt.audio.types import (
    AudioFrame,
    AudioSourceError,
    FloatAudio,
    SourceState,
    SourceStats,
)


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    host_api: str
    max_channels: int
    default_sample_rate: float
    is_default: bool


def input_devices() -> list[InputDevice]:
    """Enumerate endpoints; indices are local to the current PortAudio session."""
    try:
        apis = sd.query_hostapis()
        default = int(sd.default.device[0])
        return [
            InputDevice(
                i,
                d["name"],
                apis[d["hostapi"]]["name"],
                d["max_input_channels"],
                d["default_samplerate"],
                i == default,
            )
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]
    except sd.PortAudioError as exc:
        raise AudioSourceError("Mikrofonlista nem olvasható") from exc


class _Stream(Protocol):
    @property
    def active(self) -> bool: ...
    def start(self) -> object: ...
    def abort(self, ignore_errors: bool = True) -> None: ...
    def close(self, ignore_errors: bool = True) -> None: ...


class _CallbackRing:
    """SPSC publication order, CPython 3.11 GIL. No locks or waiting in push.

    Only the producer writes `written`; only the consumer writes `read_count`.
    A slot is published after copying, and released after the reader's copy.
    NumPy may release the GIL during either copy; neither slot can be reused then.
    """

    def __init__(self, capacity: int, frames: int, channels: int) -> None:
        self.data = np.empty((capacity, frames, channels), dtype=np.float32)
        self.starts = [0] * capacity
        self.lengths = [0] * capacity
        self.capacity = capacity
        self.frames = frames
        self.written = 0
        self.read_count = 0
        self.input_blocks = 0
        self.input_samples = 0
        self.dropped_blocks = 0
        self.dropped_samples = 0
        self.overflow_events = 0
        self.max_queue = 0
        self.error: str | None = None

    def push(self, data: FloatAudio, frames: int, overflow: bool) -> None:
        start = self.input_samples
        self.input_samples += frames
        self.input_blocks += 1
        if overflow:
            self.overflow_events += 1
            self.error = "PortAudio bemeneti túlcsordulás; a hang folytonossága elveszett"
        if frames < 1 or frames > self.frames or data.shape != (frames, self.data.shape[2]):
            self.error = "Váratlan capture blokkformátum"
        if self.written - self.read_count >= self.capacity:
            self.error = "Mikrofonpuffer megtelt; a hang folytonossága elveszett"
        if self.error is not None:
            self.dropped_blocks += 1
            self.dropped_samples += frames
            return
        slot = self.written % self.capacity
        self.data[slot, :frames] = data
        self.starts[slot] = start
        self.lengths[slot] = frames
        self.written += 1
        self.max_queue = max(self.max_queue, self.written - self.read_count)

    def pop(self) -> tuple[FloatAudio, int] | None:
        if self.read_count == self.written:
            return None
        slot = self.read_count % self.capacity
        copied = self.data[slot, : self.lengths[slot]].copy()
        start = self.starts[slot]
        self.read_count += 1
        return copied, start

    def clear(self) -> None:
        # Only after the producer stream has stopped.
        self.data.fill(0)
        self.read_count = self.written


class MicrophoneSource:
    """Pull frames outside the callback. Stop discards queued/private audio.

    Call start/read/stop/close from one controller/worker, never from the callback.
    No decoder, UI or caller-provided function is invoked by the callback.
    """

    def __init__(
        self,
        device: int,
        *,
        sample_rate: int = 48000,
        channels: int = 1,
        frame_ms: int = 20,
        queue_blocks: int = 25,
        stall_seconds: float = 2.0,
    ) -> None:
        AudioNormalizer(sample_rate, channels, frame_ms=frame_ms)
        if type(device) is not int or device < 0 or not 2 <= queue_blocks <= 500:
            raise ValueError("Use a device index and 2..500 queue blocks")
        if not math.isfinite(stall_seconds) or not 0.1 <= stall_seconds <= 30:
            raise ValueError("Stall timeout must be 0.1..30 seconds")
        if sample_rate * frame_ms % 1000:
            raise ValueError("Capture block must contain an integer number of samples")
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_ms = frame_ms
        self.queue_blocks = queue_blocks
        self.stall_seconds = stall_seconds
        self.state = SourceState.IDLE
        self.error: str | None = None
        self._stream: _Stream | None = None
        self._ring: _CallbackRing | None = None
        self._normalizer = AudioNormalizer(
            sample_rate, channels, frame_ms=frame_ms, source="microphone"
        )
        self._pending: deque[AudioFrame] = deque()
        self._unexpected_end = False
        self._stopping = False
        self._cleanup_failed = False
        self._output_frames = 0
        self._output_samples = 0

    def _callback(self, data: FloatAudio, frames: int, timing: object, status: object) -> None:
        ring = self._ring
        if ring is not None and not self._stopping:
            try:
                ring.push(data, frames, bool(status))
            except Exception:
                ring.error = "Capture callback hiba"

    def _finished(self) -> None:
        if not self._stopping:
            self._unexpected_end = True

    def start(self) -> None:
        if self.state in (SourceState.RUNNING, SourceState.CLOSED):
            raise AudioSourceError("A forrás már fut vagy véglegesen lezárt")
        if self._cleanup_failed:
            raise AudioSourceError("Sikertelen driverlezárás után új forráspéldány szükséges")
        self.error = None
        self._normalizer.reset()
        self._pending.clear()
        self._output_frames = self._output_samples = 0
        self._unexpected_end = self._stopping = False
        self._ring = _CallbackRing(
            self.queue_blocks, self.sample_rate * self.frame_ms // 1000, self.channels
        )
        self._observed_samples = 0
        self._progress_time = time.monotonic()
        try:
            sd.check_input_settings(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype="float32",
            )
            self._stream = cast(
                _Stream,
                sd.InputStream(
                    device=self.device,
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    dtype="float32",
                    blocksize=self._ring.frames,
                    callback=self._callback,
                    finished_callback=self._finished,
                ),
            )
            self.state = SourceState.RUNNING
            self._stream.start()
        except Exception as exc:
            self._fail("A kiválasztott mikrofon nem indítható", exc)

    def _release(self) -> str | None:
        self._stopping = True
        stream, self._stream = self._stream, None
        cleanup_error = None
        try:
            if stream is not None:
                try:
                    stream.abort(ignore_errors=True)
                except Exception:
                    cleanup_error = "Mikrofon leállítási hiba (abort)"
                try:
                    stream.close(ignore_errors=False)
                except Exception:
                    self._cleanup_failed = True
                    cleanup_error = "Mikrofon erőforráslezárási hiba (close)"
        finally:
            if self._ring is not None:
                self._ring.clear()
            self._pending.clear()
            self._normalizer.reset()
        return cleanup_error

    def _fail(self, message: str, cause: Exception | None = None) -> None:
        cleanup_error = self._release()
        self.error = message if cleanup_error is None else f"{message}; {cleanup_error}"
        self.state = SourceState.ERROR
        raise AudioSourceError(self.error) from cause

    def read(self, timeout: float = 0.1) -> AudioFrame | None:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Timeout must be finite and nonnegative")
        if self.state == SourceState.ERROR:
            raise AudioSourceError(self.error)
        if self.state != SourceState.RUNNING:
            return None
        deadline = time.monotonic() + timeout
        while True:
            ring, stream = self._ring, self._stream
            assert ring is not None and stream is not None
            if ring.error:
                self._fail(ring.error)
            try:
                active = stream.active
            except Exception as exc:
                self._fail("Mikrofoneszköz állapota nem olvasható", exc)
            if self._unexpected_end or not active:
                self._fail("A mikrofon váratlanul leállt vagy az eszköz levált")
            if self._pending:
                frame = self._pending.popleft()
                self._output_frames += 1
                self._output_samples += len(frame.samples)
                return frame
            block = ring.pop()
            if block is not None:
                data, start = block
                try:
                    self._pending.extend(self._normalizer.push(data, start_sample=start))
                except Exception as exc:
                    self._fail("Mikrofonhang átalakítása sikertelen", exc)
                continue
            now = time.monotonic()
            if ring.input_samples != self._observed_samples:
                self._observed_samples = ring.input_samples
                self._progress_time = now
            if now - self._progress_time >= self.stall_seconds:
                self._fail("A mikrofon nem küld hangblokkokat (capture timeout)")
            if now >= deadline:
                return None
            time.sleep(min(0.002, deadline - now))

    def stop(self) -> None:
        if self.state == SourceState.CLOSED:
            return
        cleanup_error = self._release()
        if cleanup_error is not None:
            self.error = cleanup_error
            self.state = SourceState.ERROR
            raise AudioSourceError(cleanup_error)
        if self.state != SourceState.ERROR:
            self.state = SourceState.STOPPED

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self.state = SourceState.CLOSED

    @property
    def stats(self) -> SourceStats:
        r = self._ring
        if r is None:
            return SourceStats()
        return SourceStats(
            r.input_blocks,
            r.input_samples,
            r.dropped_blocks,
            r.dropped_samples,
            r.overflow_events,
            self._output_frames,
            self._output_samples,
            r.max_queue,
        )
