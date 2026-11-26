"""Backend-independent synchronous engine contract. Drive it from a worker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from offline_stt.audio.types import AudioFrame


class EngineError(RuntimeError):
    """Visible model/decoder/lifecycle failure; never a network fallback."""


class EngineInputError(ValueError):
    """An unaccepted audio block; caller can correct/retry it without data loss."""


class EngineBufferFull(EngineInputError):
    """Flush or reset before retrying; the rejected block was not consumed."""


class EngineState(Enum):
    UNLOADED = "unloaded"
    READY = "ready"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class DecodedSegment:
    start_sample: int
    end_sample: int
    text: str


@dataclass(frozen=True)
class DecodeResult:
    """Raw bounded-window hypothesis, not a stabilized TranscriptEvent (#19)."""

    start_sample: int
    end_sample: int
    language: str
    segments: tuple[DecodedSegment, ...]
    final: bool
    decode_seconds: float


@dataclass(frozen=True)
class EngineStats:
    model_loads: int
    warmup_calls: int
    decode_calls: int
    load_seconds: float
    warmup_seconds: float
    decode_seconds: float
    buffered_samples: int
    session_input_samples: int


class SpeechEngine(Protocol):
    """One worker, serialized calls. push_audio buffers; preview/flush decode."""

    state: EngineState
    error: str | None

    def load(self) -> None: ...
    def push_audio(self, frame: AudioFrame) -> None: ...
    def preview(self) -> DecodeResult: ...
    def flush(self) -> DecodeResult: ...
    def reset(self, *, start_sample: int = 0) -> None: ...
    def close(self) -> None: ...
    @property
    def stats(self) -> EngineStats: ...
