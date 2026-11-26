"""Local CPU INT8 baseline. All neural work is synchronous and worker-owned."""

from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from offline_stt.audio.types import OUTPUT_RATE, AudioFrame, FloatAudio
from offline_stt.config import Config
from offline_stt.engines.models import LocalModelStore, VerifiedModel
from offline_stt.engines.types import (
    DecodedSegment,
    DecodeResult,
    EngineBufferFull,
    EngineError,
    EngineInputError,
    EngineState,
    EngineStats,
)


@dataclass(frozen=True)
class BackendSegment:
    start: float
    end: float
    text: str


class Decoder(Protocol):
    device: str
    compute_type: str
    multilingual: bool

    def decode(
        self, audio: FloatAudio, language: str, max_new_tokens: int
    ) -> Iterable[BackendSegment]: ...
    def close(self) -> None: ...


class WhisperDecoder:
    """The only SDK-dependent boundary. Never pass an identifier to WhisperModel."""

    def __init__(self, verified: VerifiedModel, cpu_threads: int) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        self._model = WhisperModel(
            str(verified.path),
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
            num_workers=1,
            local_files_only=True,
        )
        self.device = str(self._model.model.device)
        self.compute_type = str(self._model.model.compute_type)
        self.multilingual = bool(self._model.model.is_multilingual)

    def decode(
        self, audio: FloatAudio, language: str, max_new_tokens: int
    ) -> Iterable[BackendSegment]:
        segments, _ = self._model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt=None,
            vad_filter=False,
            word_timestamps=False,
            max_new_tokens=max_new_tokens,
            log_progress=False,
        )
        # The SDK generator is lazy; iterating here performs the neural work.
        for segment in segments:
            yield BackendSegment(float(segment.start), float(segment.end), str(segment.text))

    def close(self) -> None:
        self._model.model.unload_model()


@dataclass(frozen=True)
class EngineOptions:
    language: str = "hu"
    cpu_threads: int = 4
    max_audio_seconds: float = 12.0
    max_new_tokens: int = 224

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z]{2,3}", self.language):
            raise ValueError("Expected a 2..3 lowercase language code")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 64:
            raise ValueError("CPU threads must be 1..64")
        if not math.isfinite(self.max_audio_seconds) or not 0.02 <= self.max_audio_seconds <= 60:
            raise ValueError("Audio window must be 0.02..60 seconds")
        if type(self.max_new_tokens) is not int or not 1 <= self.max_new_tokens <= 448:
            raise ValueError("Token limit must be 1..448")


DecoderFactory = Callable[[VerifiedModel, int], Decoder]


class FasterWhisperEngine:
    """Bounded-window adapter; #6/#19 own VAD, scheduling and stable events.

    A successful load is idempotent. reset clears session audio, not the model.
    preview gives an unstable snapshot; flush decodes and consumes the window.
    No method saves audio/transcripts or loads a replacement model implicitly.
    """

    def __init__(
        self,
        store: LocalModelStore,
        model_id: str = "base-multilingual",
        *,
        options: EngineOptions = EngineOptions(),
        decoder_factory: DecoderFactory = WhisperDecoder,
    ) -> None:
        store.catalog.get(model_id)
        self.store = store
        self.model_id = model_id
        self.options = options
        self.state = EngineState.UNLOADED
        self.error: str | None = None
        self.compute_type: str | None = None
        self._factory = decoder_factory
        self._decoder: Decoder | None = None
        self._buffer = np.zeros(
            math.ceil(options.max_audio_seconds * OUTPUT_RATE), dtype=np.float32
        )
        self._count = 0
        self._start = self._next = self._session_samples = 0
        self._source: str | None = None
        self._loads = self._warmups = self._decodes = 0
        self._load_seconds = self._warmup_seconds = self._decode_seconds = 0.0

    @classmethod
    def from_config(cls, config: Config, store: LocalModelStore) -> FasterWhisperEngine:
        return cls(
            store,
            config.engine.model,
            options=EngineOptions(
                language=config.application.language,
                max_audio_seconds=config.vad.max_segment_ms / 1000,
            ),
        )

    def _clear(self) -> None:
        self._buffer.fill(0)
        self._count = 0
        self._source = None

    def _require_ready(self) -> Decoder:
        if self.state != EngineState.READY or self._decoder is None:
            raise EngineError("Engine is not ready; explicitly load/reset it first")
        return self._decoder

    def load(self) -> None:
        if self.state == EngineState.READY:
            return
        if self.state == EngineState.CLOSED or self._decoder is not None:
            raise EngineError("Cannot load a closed/failed engine; reset or create a new instance")
        self.error = None
        self._clear()
        try:
            verified = self.store.verify(self.model_id)
            started = time.perf_counter()
            try:
                self._decoder = self._factory(verified, self.options.cpu_threads)
                self._loads += 1
            finally:
                self._load_seconds += time.perf_counter() - started
            if (
                self._decoder.device != "cpu"
                or not self._decoder.multilingual
                or self._decoder.compute_type not in ("int8", "int8_float32")
            ):
                raise EngineError("Backend did not load a multilingual CPU INT8 model")
            self.compute_type = self._decoder.compute_type
            started = time.perf_counter()
            self._warmups += 1
            try:
                # Consume the lazy generator. Warm-up is never counted as a decode.
                for _ in self._decoder.decode(
                    np.zeros(OUTPUT_RATE, dtype=np.float32), self.options.language, 1
                ):
                    pass
            finally:
                self._warmup_seconds += time.perf_counter() - started
            self.state = EngineState.READY
        except Exception as exc:
            decoder, self._decoder = self._decoder, None
            cleanup = ""
            if decoder is not None:
                try:
                    decoder.close()
                except Exception:
                    cleanup = "; backend cleanup also failed"
            self.error = f"Local model load failed: {exc}{cleanup}"
            self.state = EngineState.ERROR
            raise EngineError(self.error) from exc

    def push_audio(self, frame: AudioFrame) -> None:
        self._require_ready()
        if frame.start_sample != self._next:
            raise EngineInputError("Audio sample clock is discontinuous; reset with the new origin")
        if self._source is not None and frame.source != self._source:
            raise EngineInputError("Do not mix audio sources within one engine window")
        if self._count + len(frame.samples) > len(self._buffer):
            raise EngineBufferFull("Engine window is full; block not consumed, flush/reset first")
        self._buffer[self._count : self._count + len(frame.samples)] = frame.samples
        self._count += len(frame.samples)
        self._session_samples += len(frame.samples)
        self._next = frame.end_sample
        self._source = frame.source

    def _decode(self, final: bool) -> DecodeResult:
        decoder = self._require_ready()
        start, end = self._start, self._next
        if not self._count:
            return DecodeResult(start, end, self.options.language, (), final, 0.0)
        audio = self._buffer[: self._count].copy()
        started = time.perf_counter()
        self._decodes += 1
        try:
            result = []
            for segment in decoder.decode(
                audio, self.options.language, self.options.max_new_tokens
            ):
                if (
                    not math.isfinite(segment.start)
                    or not math.isfinite(segment.end)
                    or segment.start < 0
                    or segment.end < segment.start
                ):
                    raise EngineError("Backend returned invalid segment timestamps")
                begin = min(end, start + round(segment.start * OUTPUT_RATE))
                finish = min(end, start + round(segment.end * OUTPUT_RATE))
                if segment.text.strip() and finish > begin:
                    result.append(DecodedSegment(begin, finish, segment.text))
            elapsed = time.perf_counter() - started
            decoded = DecodeResult(start, end, self.options.language, tuple(result), final, elapsed)
        except Exception as exc:
            self._clear()
            self.error = "Decode failed; reset the session explicitly"
            self.state = EngineState.ERROR
            raise EngineError(self.error) from exc
        finally:
            self._decode_seconds += time.perf_counter() - started
            audio.fill(0)
        if final:
            self._clear()
            self._start = self._next
        return decoded

    def preview(self) -> DecodeResult:
        return self._decode(False)

    def flush(self) -> DecodeResult:
        return self._decode(True)

    def reset(self, *, start_sample: int = 0) -> None:
        if self.state == EngineState.CLOSED:
            raise EngineError("Closed engine cannot be reset")
        if type(start_sample) is not int or start_sample < 0:
            raise EngineInputError("Session origin must be a nonnegative sample index")
        self._clear()
        self._start = self._next = start_sample
        self._session_samples = 0
        self.error = None
        self.state = EngineState.READY if self._decoder is not None else EngineState.UNLOADED

    def close(self) -> None:
        decoder, self._decoder = self._decoder, None
        self._clear()
        self.state = EngineState.CLOSED
        if decoder is not None:
            try:
                decoder.close()
            except Exception as exc:
                self.error = "Backend unload failed"
                raise EngineError(self.error) from exc

    @property
    def stats(self) -> EngineStats:
        return EngineStats(
            self._loads,
            self._warmups,
            self._decodes,
            self._load_seconds,
            self._warmup_seconds,
            self._decode_seconds,
            self._count,
            self._session_samples,
        )
