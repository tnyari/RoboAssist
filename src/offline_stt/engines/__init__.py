"""Worker-driven local model engines. Importing never loads or downloads a model."""

from offline_stt.engines.models import LocalModelStore, ModelCatalog, ModelError
from offline_stt.engines.types import (
    DecodedSegment,
    DecodeResult,
    EngineBufferFull,
    EngineError,
    EngineInputError,
    EngineState,
    SpeechEngine,
)
from offline_stt.engines.whisper import EngineOptions, FasterWhisperEngine

__all__ = [
    "DecodeResult",
    "DecodedSegment",
    "EngineBufferFull",
    "EngineError",
    "EngineInputError",
    "EngineOptions",
    "EngineState",
    "FasterWhisperEngine",
    "LocalModelStore",
    "ModelCatalog",
    "ModelError",
    "SpeechEngine",
]
