"""Stateful libswresample conversion; never called from a capture callback."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from offline_stt.audio.types import OUTPUT_RATE, AudioFrame, FloatAudio, SourceKind
from offline_stt.native_deps import configure_av_dll_search

if TYPE_CHECKING:
    import av


class AudioNormalizer:
    """Arithmetic-mean downmix, filtered resampling and 20/30 ms framing.

    Flush zero-extends the filter input, then trims to ceil(N * 16000 / input_rate).
    It never pads the final output frame to a full frame. Reset starts a new clock.
    """

    def __init__(
        self, sample_rate: int, channels: int, *, frame_ms: int = 20, source: SourceKind = "wav"
    ) -> None:
        if type(sample_rate) is not int or not 8000 <= sample_rate <= 192000:
            raise ValueError("Input sample rate must be an integer in 8000..192000 Hz")
        if channels not in (1, 2) or frame_ms not in (20, 30):
            raise ValueError("Use mono/stereo input and 20 or 30 ms output frames")
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_samples = OUTPUT_RATE * frame_ms // 1000
        self.source = source
        self.reset()

    def reset(self) -> None:
        configure_av_dll_search()
        import av

        self._av = av
        self._resampler = av.AudioResampler(format="fltp", layout="mono", rate=OUTPUT_RATE)
        self._pending: FloatAudio = np.empty(0, dtype=np.float32)
        self.input_samples = 0
        self._accepted_output = 0
        self._emitted_output = 0
        self._flushed = False

    def _input_frame(self, mono: FloatAudio, start: int) -> av.AudioFrame:
        frame = self._av.AudioFrame.from_ndarray(mono.reshape(1, -1), format="fltp", layout="mono")
        frame.sample_rate = self.sample_rate
        frame.pts = start
        frame.time_base = Fraction(1, self.sample_rate)
        return frame

    def _collect(self, frames: list[av.AudioFrame], limit: int | None = None) -> list[AudioFrame]:
        result: list[AudioFrame] = []
        for frame in frames:
            data = np.asarray(frame.to_ndarray(), dtype=np.float32).reshape(-1)
            if limit is not None:
                data = data[: max(0, limit - self._accepted_output)]
            self._accepted_output += len(data)
            self._pending = np.concatenate((self._pending, data))
            count = len(self._pending) // self.frame_samples
            for i in range(count):
                start = i * self.frame_samples
                result.append(
                    AudioFrame(
                        self._pending[start : start + self.frame_samples],
                        self._emitted_output,
                        self.source,
                    )
                )
                self._emitted_output += self.frame_samples
            self._pending = self._pending[count * self.frame_samples :].copy()
        return result

    def push(self, samples: FloatAudio, *, start_sample: int | None = None) -> list[AudioFrame]:
        if self._flushed:
            raise ValueError("Normalizer is flushed; reset before a new session")
        if start_sample is not None and start_sample != self.input_samples:
            raise ValueError("Discontinuous input sample clock")
        if (
            samples.dtype != np.float32
            or samples.ndim != 2
            or samples.shape[1] != self.channels
            or not np.isfinite(samples).all()
        ):
            raise ValueError("Expected finite float32 audio shaped (samples, input_channels)")
        if not len(samples):
            return []
        mono = np.ascontiguousarray(samples.mean(axis=1, dtype=np.float32))
        frames = self._resampler.resample(self._input_frame(mono, self.input_samples))
        self.input_samples += len(samples)
        return self._collect(frames)

    def flush(self) -> list[AudioFrame]:
        if self._flushed:
            return []
        self._flushed = True
        if not self.input_samples:
            return []
        target = (self.input_samples * OUTPUT_RATE + self.sample_rate - 1) // self.sample_rate
        padding = np.zeros(max(64, self.sample_rate // 100), dtype=np.float32)
        frames = self._resampler.resample(self._input_frame(padding, self.input_samples))
        frames.extend(self._resampler.resample(None))
        result = self._collect(frames, target)
        if self._accepted_output != target:
            raise RuntimeError("Resampler did not produce the expected finite-stream sample count")
        if len(self._pending):
            result.append(AudioFrame(self._pending, self._emitted_output, self.source))
            self._emitted_output += len(self._pending)
            self._pending = np.empty(0, dtype=np.float32)
        return result


def decode_pcm(data: bytes, sample_width: int, channels: int) -> FloatAudio:
    """Decode uncompressed WAV PCM8/16/24/32; channel samples stay interleaved."""
    if channels not in (1, 2) or sample_width not in (1, 2, 3, 4):
        raise ValueError("Only mono/stereo PCM8/16/24/32 WAV is supported")
    if len(data) % (sample_width * channels):
        raise ValueError("Truncated WAV sample")
    if sample_width == 1:
        values = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif sample_width == 3:
        octets = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        packed = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
        signed = (packed ^ 0x800000) - 0x800000
        values = signed.astype(np.float32) / 8388608
    else:
        dtype = "<i2" if sample_width == 2 else "<i4"
        integer: NDArray[np.signedinteger] = np.frombuffer(data, dtype=dtype)
        values = integer.astype(np.float32) / (2 ** (8 * sample_width - 1))
    return np.asarray(values, dtype=np.float32).reshape(-1, channels)
