"""Deterministic energy gate and bounded segmenter; no model or network needed."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from offline_stt.audio.types import OUTPUT_RATE, AudioFrame, FloatAudio, SourceKind
from offline_stt.config import Config
from offline_stt.pipeline.scheduling import DecodeJob
from offline_stt.pipeline.types import PipelineError


class EnergyVad:
    """RMS dBFS gate with separate onset/release thresholds, not semantic VAD."""

    def __init__(self, threshold_db: float, hysteresis_db: float) -> None:
        self.threshold = threshold_db
        self.hysteresis = hysteresis_db

    def speech(self, frame: AudioFrame, active: bool) -> bool:
        rms = float(np.sqrt(np.mean(np.square(frame.samples.astype(np.float64)))))
        db = 20 * math.log10(max(rms, 1e-12))
        return db >= self.threshold - (self.hysteresis if active else 0)


class Segmenter:
    def __init__(self, config: Config, submit: Callable[[DecodeJob], None]) -> None:
        self.config = config
        self.submit = submit
        self.vad = EnergyVad(config.vad.energy_threshold_db, config.vad.hysteresis_db)
        self._max = config.vad.max_segment_ms * OUTPUT_RATE // 1000
        self._pre_max = config.vad.pre_roll_ms * OUTPUT_RATE // 1000
        self._end_silence = config.vad.end_silence_ms * OUTPUT_RATE // 1000
        self._interval = config.pipeline.partial_interval_ms * OUTPUT_RATE // 1000
        self._window = min(config.pipeline.partial_window_ms * OUTPUT_RATE // 1000, self._max)
        self._buffer = np.zeros(self._max, dtype=np.float32)
        self._pre = np.zeros(self._pre_max, dtype=np.float32)
        self._pre_count = self._count = self._silence = self._next_partial = 0
        self._next = self._start = self._segment = 0
        self._source: SourceKind | None = None

    def _remember(self, samples: FloatAudio) -> None:
        size = min(len(samples), self._pre_max)
        if not size:
            return
        keep = min(self._pre_count, self._pre_max - size)
        if keep:
            self._pre[:keep] = self._pre[self._pre_count - keep : self._pre_count]
        self._pre[keep : keep + size] = samples[-size:]
        self._pre_count = keep + size

    def _emit(self, final: bool) -> None:
        assert self._source is not None and self._count
        offset = 0 if final else max(0, self._count - self._window)
        self.submit(
            DecodeJob(
                self._segment,
                self._start,
                AudioFrame(self._buffer[offset : self._count], self._start + offset, self._source),
                final,
            )
        )
        if final:
            self._buffer.fill(0)
            self._count = self._silence = 0

    def push(self, frame: AudioFrame) -> None:
        if frame.start_sample != self._next or (
            self._source is not None and self._source != frame.source
        ):
            raise PipelineError("Discontinuous session sample clock or changed source")
        self._source = frame.source
        self._next = frame.end_sample
        speaking = self.vad.speech(frame, bool(self._count))
        if not self._count:
            if not speaking:
                self._remember(frame.samples)
                return
            self._segment += 1
            self._start = frame.start_sample - self._pre_count
            self._buffer[: self._pre_count] = self._pre[: self._pre_count]
            self._count = self._pre_count
            self._pre.fill(0)
            self._pre_count = 0
            self._next_partial = self._interval
        offset = 0
        while offset < len(frame.samples):
            take = min(len(frame.samples) - offset, self._max - self._count)
            self._buffer[self._count : self._count + take] = frame.samples[offset : offset + take]
            self._count += take
            offset += take
            self._silence = 0 if speaking else self._silence + take
            if self._count == self._max or self._silence >= self._end_silence:
                end = self._start + self._count
                self._emit(True)
                if offset < len(frame.samples):
                    if not speaking:
                        self._remember(frame.samples[offset:])
                        break
                    self._segment += 1
                    self._start = end
                    self._next_partial = self._interval
            elif self._count >= self._next_partial:
                self._emit(False)
                self._next_partial = self._count + self._interval

    def flush(self) -> None:
        if self._count:
            self._emit(True)
        self._pre.fill(0)
        self._pre_count = 0
