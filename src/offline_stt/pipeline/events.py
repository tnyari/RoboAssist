"""Session-scoped revisions and bounded provisional rolling-window alignment."""

from __future__ import annotations

import time
from collections.abc import Callable

from offline_stt.engines.types import DecodeResult
from offline_stt.pipeline.scheduling import DecodeJob
from offline_stt.pipeline.types import PipelineError, TranscriptEvent


def _words(text: str) -> list[str]:
    return [word.casefold().strip('.,!?…:;"„”()') for word in text.split()]


def _prefix(left: str, right: str) -> str:
    a, b = _words(left), _words(right)
    count = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        count += 1
    return " ".join(right.split()[:count])


def _overlap(left: str, right: str) -> str:
    a, b = _words(left), _words(right)
    for size in range(min(len(a), len(b)), 0, -1):
        if a[-size:] == b[:size]:
            return " ".join(left.split() + right.split()[size:])
    return right  # Alignment is uncertain: replace provisional text; final is authoritative.


class Stabilizer:
    """Only final text is immutable. An agreed partial prefix is provisional."""

    def __init__(self, session_id: str, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.session_id = session_id
        self._clock = clock
        self._epoch = clock()
        self._emitted = 0.0
        self._segment = self._finalized = self._revision = 0
        self._text = self._stable = ""
        self._window_start = self._window_end = 0

    def accept(self, job: DecodeJob, result: DecodeResult) -> TranscriptEvent | None:
        if job.segment <= self._finalized or job.segment < self._segment:
            return None
        if job.segment != self._segment:
            self._segment = job.segment
            self._revision = 0
            self._text = self._stable = ""
            self._window_start = self._window_end = job.frame.start_sample
        # Deduplicate only repeated backend segments that overlap in audio time.
        parts: list[str] = []
        previous_end = -1
        for segment in result.segments:
            text = " ".join(segment.text.split())
            if not text:
                continue
            if parts and segment.start_sample < previous_end and _words(parts[-1]) == _words(text):
                previous_end = max(previous_end, segment.end_sample)
                continue
            parts.append(text)
            previous_end = segment.end_sample
        text = " ".join(parts)
        if not job.final and job.frame.start_sample > self._window_start:
            if job.frame.start_sample < self._window_end:
                text = _overlap(self._text, text)
        if len(text) > 32768:
            raise PipelineError("Transcript exceeds the bounded event text limit")
        stable = text if job.final else _prefix(self._text, text)
        changed = text != self._text or stable != self._stable
        self._window_start = job.frame.start_sample
        self._window_end = job.frame.end_sample
        self._text, self._stable = text, stable
        if not job.final and (not text or not changed):
            return None
        self._revision += 1
        if job.final:
            self._finalized = job.segment
        self._emitted = max(self._emitted, (self._clock() - self._epoch) * 1000)
        return TranscriptEvent(
            1,
            self.session_id,
            f"{self.session_id}:{job.segment}",
            self._revision,
            job.frame.source,
            result.language,
            "final" if job.final else "partial",
            job.segment_start / 16,
            job.frame.end_sample / 16,
            text,
            self._emitted,
            stable,
        )
