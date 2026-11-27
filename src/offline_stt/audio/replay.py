"""Local PCM WAV replay on absolute monotonic, session-relative deadlines."""

from __future__ import annotations

import math
import time
import wave
from collections import deque
from collections.abc import Callable
from pathlib import Path

from offline_stt.audio.normalize import AudioNormalizer, decode_pcm
from offline_stt.audio.types import (
    OUTPUT_RATE,
    AudioFrame,
    AudioSourceError,
    SourceState,
    SourceStats,
)


class WavReplaySource:
    def __init__(
        self,
        path: str | Path,
        *,
        frame_ms: int = 20,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if frame_ms not in (20, 30):
            raise ValueError("Use 20 or 30 ms frames")
        self.path = Path(path)
        self.frame_ms = frame_ms
        self.state = SourceState.IDLE
        self.error: str | None = None
        self._clock = clock
        self._sleep = sleep
        self._file: wave.Wave_read | None = None
        self._normalizer: AudioNormalizer | None = None
        self._pending: deque[AudioFrame] = deque()
        self._input_blocks = self._input_samples = 0
        self._output_frames = self._output_samples = 0
        self._eof = False

    def start(self) -> None:
        if self.state in (SourceState.RUNNING, SourceState.CLOSED):
            raise AudioSourceError("A forrás már fut vagy véglegesen lezárt")
        self.stop()
        self.error = None
        self._input_blocks = self._input_samples = 0
        self._output_frames = self._output_samples = 0
        self._eof = False
        try:
            self._file = wave.open(str(self.path), "rb")
            self.sample_rate = self._file.getframerate()
            self.channels = self._file.getnchannels()
            self.sample_width = self._file.getsampwidth()
            if self._file.getcomptype() != "NONE" or self.sample_width not in (1, 2, 3, 4):
                raise ValueError("Only uncompressed PCM8/16/24/32 WAV is supported")
            self._declared_samples = self._file.getnframes()
            self._normalizer = AudioNormalizer(
                self.sample_rate, self.channels, frame_ms=self.frame_ms, source="wav"
            )
            self._started = self._clock()
            self.state = SourceState.RUNNING
        except Exception as exc:
            self._fail(
                f"A WAV fájl nem nyitható meg támogatott helyi PCM hangként "
                f"({type(exc).__name__}{_errno_suffix(exc)})",
                exc,
            )

    def _close_file(self) -> None:
        stream, self._file = self._file, None
        if stream is not None:
            stream.close()

    def _fail(self, message: str, cause: Exception) -> None:
        self.error = message
        self.stop()
        self.state = SourceState.ERROR
        raise AudioSourceError(message) from cause

    def _feed(self) -> None:
        assert self._normalizer is not None and self._file is not None
        count = max(1, self.sample_rate * 20 // 1000)
        raw = self._file.readframes(count)
        if raw:
            audio = decode_pcm(raw, self.sample_width, self.channels)
            self._pending.extend(self._normalizer.push(audio, start_sample=self._input_samples))
            self._input_samples += len(audio)
            self._input_blocks += 1
        else:
            if self._input_samples != self._declared_samples:
                raise ValueError("WAV data is shorter than its declared sample count")
            self._pending.extend(self._normalizer.flush())
            self._eof = True
            self._close_file()

    def read(self, timeout: float = 0.1) -> AudioFrame | None:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Timeout must be finite and nonnegative")
        if self.state == SourceState.ERROR:
            raise AudioSourceError(self.error)
        if self.state != SourceState.RUNNING:
            return None
        deadline = self._clock() + timeout
        while self.state == SourceState.RUNNING:
            if not self._pending:
                if self._eof:
                    self.state = SourceState.ENDED
                    return None
                try:
                    self._feed()
                except Exception as exc:
                    self._fail(
                        f"WAV olvasási vagy átalakítási hiba "
                        f"({type(exc).__name__}{_errno_suffix(exc)})",
                        exc,
                    )
                continue
            due = self._started + self._pending[0].end_sample / OUTPUT_RATE
            now = self._clock()
            if now < due:
                if now >= deadline:
                    return None
                self._sleep(min(due - now, deadline - now, 0.02))
                continue
            frame = self._pending.popleft()
            self._output_frames += 1
            self._output_samples += len(frame.samples)
            if self._eof and not self._pending:
                self.state = SourceState.ENDED
            return frame
        return None

    def stop(self) -> None:
        self._close_file()
        self._pending.clear()
        if self._normalizer is not None:
            self._normalizer.reset()
        if self.state not in (SourceState.CLOSED, SourceState.ERROR):
            self.state = SourceState.STOPPED

    def close(self) -> None:
        self.stop()
        self.state = SourceState.CLOSED

    @property
    def stats(self) -> SourceStats:
        return SourceStats(
            input_blocks=self._input_blocks,
            input_samples=self._input_samples,
            output_frames=self._output_frames,
            output_samples=self._output_samples,
        )


def _errno_suffix(exc: Exception) -> str:
    """Expose safe OS error codes without putting local paths in UI/IPC errors."""
    code = getattr(exc, "errno", None)
    return f", errno={code}" if isinstance(code, int) else ""
