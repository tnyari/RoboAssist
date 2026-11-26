"""Audio contracts. A source has one reader; lifecycle calls are serialized."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

FloatAudio = NDArray[np.float32]
SourceKind = Literal["microphone", "wav"]
OUTPUT_RATE = 16000


class AudioSourceError(RuntimeError):
    """Visible capture/file/discontinuity failure; never silently repair lost audio."""


class SourceState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ENDED = "ended"
    STOPPED = "stopped"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class AudioFrame:
    """Owned mono float32 samples on a session-relative 16 kHz sample clock."""

    samples: FloatAudio
    start_sample: int
    source: SourceKind

    def __post_init__(self) -> None:
        if self.start_sample < 0 or self.samples.ndim != 1 or not len(self.samples):
            raise ValueError("A frame needs nonempty mono audio and a nonnegative sample index")
        if self.samples.dtype != np.float32 or not np.isfinite(self.samples).all():
            raise ValueError("A frame needs finite float32 samples")
        owned = self.samples.copy()
        owned.setflags(write=False)
        object.__setattr__(self, "samples", owned)

    @property
    def end_sample(self) -> int:
        return self.start_sample + len(self.samples)

    @property
    def start_ms(self) -> float:
        return self.start_sample * 1000 / OUTPUT_RATE

    @property
    def end_ms(self) -> float:
        return self.end_sample * 1000 / OUTPUT_RATE


@dataclass(frozen=True)
class SourceStats:
    input_blocks: int = 0
    input_samples: int = 0
    dropped_blocks: int = 0
    dropped_samples: int = 0
    overflow_events: int = 0
    output_frames: int = 0
    output_samples: int = 0
    max_queue_blocks: int = 0


class AudioSource(Protocol):
    state: SourceState
    error: str | None

    def start(self) -> None: ...
    def read(self, timeout: float = 0.1) -> AudioFrame | None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    @property
    def stats(self) -> SourceStats: ...


def pcm16_bytes(samples: FloatAudio) -> bytes:
    """Little-endian signed PCM16 with rounding and saturation, not wrapping."""
    if samples.ndim != 1 or not np.isfinite(samples).all():
        raise ValueError("PCM16 conversion needs finite mono audio")
    scaled = np.clip(np.rint(samples.astype(np.float64) * 32768), -32768, 32767)
    return scaled.astype("<i2").tobytes()
