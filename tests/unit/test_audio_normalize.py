"""Signal and boundary checks independent of microphone hardware."""

import numpy as np
import pytest

from offline_stt.audio import AudioNormalizer, pcm16_bytes
from offline_stt.audio.normalize import decode_pcm


def convert(data, rate, channels, sizes, frame_ms=20):
    normalizer = AudioNormalizer(rate, channels, frame_ms=frame_ms)
    frames = []
    pos = 0
    for size in sizes:
        end = min(pos + size, len(data))
        frames.extend(normalizer.push(data[pos:end], start_sample=pos))
        pos = end
    if pos < len(data):
        frames.extend(normalizer.push(data[pos:], start_sample=pos))
    frames.extend(normalizer.flush())
    assert normalizer.flush() == []
    assert [f.start_sample for f in frames] == [
        sum(len(p.samples) for p in frames[:i]) for i in range(len(frames))
    ]
    assert all(f.samples.dtype == np.float32 and not f.samples.flags.writeable for f in frames)
    assert all(len(f.samples) == frame_ms * 16 for f in frames[:-1])
    output = np.concatenate([f.samples for f in frames]) if frames else np.empty(0)
    return output, frames


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("frame_ms", [20, 30])
def test_filtered_resampling_is_independent_of_callback_boundaries(rate, channels, frame_ms):
    count = rate + 137
    sine = (0.2 + 0.3 * np.sin(2 * np.pi * 1000 * np.arange(count) / rate)).astype("float32")
    data = np.column_stack([sine] * channels)
    whole, frames = convert(data, rate, channels, [len(data)], frame_ms)
    chunked, _ = convert(data, rate, channels, [1, 27, 334, 882] * 60, frame_ms)
    np.testing.assert_allclose(whole, chunked, atol=2e-6)
    expected_count = (count * 16000 + rate - 1) // rate
    assert len(whole) == expected_count
    expected = 0.2 + 0.3 * np.sin(2 * np.pi * 1000 * np.arange(len(whole)) / 16000)
    np.testing.assert_allclose(whole[100:-100], expected[100:-100], atol=1e-3)
    assert frames[-1].end_ms == pytest.approx(len(whole) / 16)


@pytest.mark.parametrize("rate", [44100, 48000])
def test_antialias_filter_rejects_above_nyquist(rate):
    signal = (0.5 * np.sin(2 * np.pi * 12000 * np.arange(rate) / rate)).astype("float32")
    output, _ = convert(signal.reshape(-1, 1), rate, 1, [rate // 50] * 50)
    assert np.sqrt(np.mean(output[200:-200] ** 2)) < 0.002


@pytest.mark.parametrize("rate", [8000, 16000, 44100, 48000])
@pytest.mark.parametrize("count", [0, 1, 2, 17, 321, 1001])
def test_finite_stream_keeps_exact_sample_count_including_very_short_files(rate, count):
    output, _ = convert(np.full((count, 1), 0.25, dtype="float32"), rate, 1, [count])
    assert len(output) == (count * 16000 + rate - 1) // rate
    assert np.isfinite(output).all()


def test_stereo_downmix_reset_and_discontinuity():
    n = AudioNormalizer(48000, 2)
    data = np.tile(np.array([0.2, 0.6], dtype="float32"), (4800, 1))
    with pytest.raises(ValueError, match="Discontinuous"):
        n.push(data, start_sample=1)
    frames = n.push(data) + n.flush()
    np.testing.assert_allclose(np.concatenate([f.samples for f in frames])[50:-50], 0.4, atol=1e-5)
    with pytest.raises(ValueError, match="flushed"):
        n.push(data)
    n.reset()
    assert n.push(data)[0].start_sample == 0


@pytest.mark.parametrize(
    "data",
    [
        np.zeros((5, 2), dtype="float32"),
        np.zeros((5, 1), dtype="float64"),
        np.full((5, 1), np.nan, dtype="float32"),
    ],
)
def test_invalid_input_does_not_advance_clock(data):
    n = AudioNormalizer(48000, 1)
    with pytest.raises(ValueError):
        n.push(data)
    assert n.input_samples == 0


def test_pcm16_rounding_saturation_and_little_endian():
    data = np.array([-2, -1, -0.5, 0, 0.5, 1, 2], dtype="float32")
    assert np.frombuffer(pcm16_bytes(data), dtype="<i2").tolist() == [
        -32768,
        -32768,
        -16384,
        0,
        16384,
        32767,
        32767,
    ]


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_wav_pcm_integer_extrema(width):
    if width == 1:
        raw = bytes([0, 128, 255])
    else:
        n = 2 ** (width * 8 - 1)
        raw = b"".join(v.to_bytes(width, "little", signed=True) for v in (-n, 0, n - 1))
    output = decode_pcm(raw, width, 1).reshape(-1)
    np.testing.assert_allclose(output, [-1, 0, 1 - 2 ** (1 - width * 8)], atol=1e-7)
    with pytest.raises(ValueError):
        decode_pcm(b"x", 2, 1)
