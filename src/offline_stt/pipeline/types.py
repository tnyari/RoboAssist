"""Immutable public session data; no UI, backend or capture dependency."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from offline_stt.audio.types import SourceKind


class PipelineError(RuntimeError):
    """Visible source, decoder, overload or lifecycle failure."""


class SessionState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class TranscriptEvent:
    schema_version: int
    session_id: str
    segment_id: str
    revision: int
    source: SourceKind
    language: str
    type: Literal["partial", "final"]
    audio_start_ms: float
    audio_end_ms: float
    text: str
    emitted_monotonic_ms: float
    stable_prefix: str = ""
    confidence: None = None  # No calibrated probability is provided by this adapter.


@dataclass(frozen=True)
class PipelineStats:
    input_level_dbfs: float = -120.0
    decoder_busy: bool = False
    audio_frames: int = 0
    audio_samples: int = 0
    dropped_frames: int = 0
    dropped_samples: int = 0
    max_frame_backlog: int = 0
    frame_backlog: int = 0
    max_job_backlog: int = 0
    job_backlog: int = 0
    partial_jobs_dropped: int = 0
    final_jobs_rejected: int = 0
    partial_decodes: int = 0
    final_decodes: int = 0
    engine_model_loads: int = 0
    engine_warmup_calls: int = 0
    decoded_audio_samples: int = 0
    repeated_decode_samples: int = 0
    partial_decode_seconds: float = 0.0
    final_decode_seconds: float = 0.0
    forced_terminations: int = 0
    output_partial_dropped: int = 0
    output_final_failures: int = 0
