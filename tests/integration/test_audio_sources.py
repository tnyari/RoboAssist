"""Synthetic WAV and fake-driver integration. No real microphone in normal CI."""

import time
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from offline_stt.audio import (
    AudioSourceError,
    MicrophoneSource,
    SourceState,
    WavReplaySource,
    input_devices,
)
from offline_stt.audio import microphone as mic


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def write_wav(path, rate=48000, channels=1, width=2, count=4800):
    n = 2 ** (width * 8 - 1)
    signal = np.rint(0.25 * np.sin(2 * np.pi * 1000 * np.arange(count) / rate) * n)
    values = np.repeat(signal.astype("int64"), channels)
    if width == 1:
        raw = (values + 128).astype("uint8").tobytes()
    else:
        raw = b"".join(int(v).to_bytes(width, "little", signed=True) for v in values)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(width)
        stream.setframerate(rate)
        stream.writeframes(raw)


@pytest.fixture
def backend(monkeypatch):
    streams = []

    class Stream:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.active = False
            self.closed = False
            streams.append(self)

        def start(self):
            self.active = True

        def feed(self, value=0.3, overflow=False):
            data = np.full(
                (self.kwargs["blocksize"], self.kwargs["channels"]), value, dtype="float32"
            )
            self.kwargs["callback"](data, len(data), None, overflow)
            data.fill(-0.9)  # PortAudio owns and may immediately reuse this memory.

        def abort(self, ignore_errors=True):
            self.active = False
            self.kwargs["finished_callback"]()

        def close(self, ignore_errors=True):
            self.closed = True

        def disconnect(self):
            self.active = False
            self.kwargs["finished_callback"]()

    monkeypatch.setattr(mic.sd, "check_input_settings", lambda **kw: None)
    monkeypatch.setattr(mic.sd, "InputStream", Stream)
    return streams


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("frame_ms", [20, 30])
def test_capture_copy_callback_boundary_and_restart(backend, monkeypatch, rate, channels, frame_ms):
    source = MicrophoneSource(7, sample_rate=rate, channels=channels, frame_ms=frame_ms)
    calls = []
    original = source._normalizer.push

    def spy(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(source._normalizer, "push", spy)
    source.start()
    assert backend[-1].kwargs["device"] == 7
    backend[-1].feed()
    backend[-1].feed()
    assert not calls  # Downmix/resampling cannot migrate into the callback.
    frame = source.read(0)
    assert calls and frame.source == "microphone" and frame.start_sample == 0
    assert len(frame.samples) == frame_ms * 16
    np.testing.assert_allclose(frame.samples[50:], 0.3, atol=1e-5)
    source.stop()
    assert backend[-1].closed and source.state == SourceState.STOPPED
    assert source.read(0) is None
    assert not source._ring.data.any()
    source.start()
    assert source.read(0) is None
    backend[-1].feed(-0.4)
    backend[-1].feed(-0.4)
    next_frame = source.read(0)
    assert next_frame.start_sample == 0
    np.testing.assert_allclose(next_frame.samples[50:], -0.4, atol=1e-5)
    source.close()
    source.close()
    with pytest.raises(AudioSourceError):
        source.start()


def test_queue_overload_fails_visibly_instead_of_compressing_time(backend):
    source = MicrophoneSource(1, queue_blocks=2)
    source.start()
    for _ in range(3):
        backend[-1].feed()
    assert source.stats.max_queue_blocks == 2
    assert source.stats.dropped_blocks == 1
    assert source.stats.dropped_samples == 960
    with pytest.raises(AudioSourceError, match="puffer"):
        source.read(0)
    assert source.state == SourceState.ERROR and backend[-1].closed
    assert not source._ring.data.any()
    source.start()
    assert source.stats.dropped_samples == 0
    source.close()


def test_driver_overflow_and_disconnect_release_resources(backend):
    source = MicrophoneSource(1)
    source.start()
    backend[-1].feed(overflow=True)
    with pytest.raises(AudioSourceError, match="túlcsordulás"):
        source.read(0)
    assert source.stats.overflow_events == 1
    source.start()
    backend[-1].disconnect()
    with pytest.raises(AudioSourceError, match="levált"):
        source.read(0)
    assert backend[-1].closed
    source.close()


def test_stalled_active_device_is_reported(backend, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(mic.time, "monotonic", clock)
    source = MicrophoneSource(1, stall_seconds=0.1)
    source.start()
    clock.now += 0.2
    with pytest.raises(AudioSourceError, match="timeout"):
        source.read(0)
    assert backend[-1].closed


@pytest.mark.parametrize("operation", ["abort", "close"])
def test_cleanup_failure_cannot_leave_running_state_or_late_audio(backend, operation):
    source = MicrophoneSource(1)
    source.start()
    stream = backend[-1]

    def fail(ignore_errors=True):
        raise OSError("injected driver failure")

    setattr(stream, operation, fail)
    with pytest.raises(AudioSourceError, match=operation):
        source.stop()
    assert source.state == SourceState.ERROR
    if operation == "abort":
        assert stream.closed  # close must still be attempted after abort failure.
    before = source.stats.input_samples
    stream.feed()
    assert source.stats.input_samples == before and not source._ring.data.any()
    if operation == "close":
        with pytest.raises(AudioSourceError, match="új forráspéldány"):
            source.start()
    source.close()
    assert source.state == SourceState.CLOSED


def test_start_failure_and_invalid_block_are_visible(backend, monkeypatch):
    source = MicrophoneSource(1)
    monkeypatch.setattr(
        mic.sd,
        "check_input_settings",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("unsupported device")),
    )
    with pytest.raises(AudioSourceError, match="indítható"):
        source.start()
    assert source.state == SourceState.ERROR
    monkeypatch.setattr(mic.sd, "check_input_settings", lambda **kw: None)
    source.start()
    backend[-1].kwargs["callback"](np.empty((961, 1), dtype="float32"), 961, None, False)
    with pytest.raises(AudioSourceError, match="blokkformátum"):
        source.read(0)
    source.close()


def test_device_enumeration_keeps_indices_host_api_and_default(monkeypatch):
    monkeypatch.setattr(mic.sd, "default", SimpleNamespace(device=(1, -1)))
    monkeypatch.setattr(mic.sd, "query_hostapis", lambda: [{"name": "Windows WASAPI"}])
    monkeypatch.setattr(
        mic.sd,
        "query_devices",
        lambda: [
            {"name": "output", "hostapi": 0, "max_input_channels": 0},
            {"name": "mic", "hostapi": 0, "max_input_channels": 2, "default_samplerate": 48000},
        ],
    )
    devices = input_devices()
    assert len(devices) == 1
    assert (devices[0].index, devices[0].host_api, devices[0].is_default) == (
        1,
        "Windows WASAPI",
        True,
    )


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_wav_replay_pcm_amplitude_sample_count_and_restart(tmp_path, rate, channels, width):
    path = tmp_path / "synthetic.wav"
    count = rate // 5 + 17
    write_wav(path, rate, channels, width, count)
    clock = Clock()
    source = WavReplaySource(path, clock=clock, sleep=clock.sleep)
    source.start()
    started = clock.now
    assert source.stats.started_monotonic == started
    assert source.read(0) is None
    frames = []
    while source.state == SourceState.RUNNING:
        f = source.read(0.1)
        if f is not None:
            frames.append(f)
            assert clock.now - started >= f.end_sample / 16000 - 1e-12
    assert source.state == SourceState.ENDED
    output = np.concatenate([f.samples for f in frames])
    assert len(output) == (count * 16000 + rate - 1) // rate
    assert [f.start_sample for f in frames] == list(range(0, len(output), 320))
    assert all(f.source == "wav" for f in frames)
    expected = 0.25 * np.sin(2 * np.pi * 1000 * np.arange(len(output)) / 16000)
    np.testing.assert_allclose(output[60:-60], expected[60:-60], atol=0.01 if width == 1 else 1e-3)
    assert clock.now - started == pytest.approx(len(output) / 16000)
    source.start()
    assert source.read(0.1).start_sample == 0
    source.stop()
    assert source.read(0) is None
    assert source._file is None and not source._pending
    source.close()
    with pytest.raises(AudioSourceError):
        source.start()


def test_replay_absolute_deadlines_do_not_accumulate_consumer_work(tmp_path):
    path = tmp_path / "clock.wav"
    write_wav(path)
    clock = Clock()
    source = WavReplaySource(path, clock=clock, sleep=clock.sleep)
    source.start()
    started = clock.now
    for index in range(5):
        frame = source.read(0.1)
        assert frame.start_sample == index * 320
        assert clock.now - started == pytest.approx((index + 1) * 0.02)
        clock.now += 0.003  # Processing time must not shift every following deadline.
    source.close()


def test_real_clock_replay_is_not_an_unpaced_file_decode(tmp_path):
    path = tmp_path / "paced.wav"
    write_wav(path)
    source = WavReplaySource(path)
    started = time.monotonic()
    source.start()
    frames = []
    while source.state == SourceState.RUNNING and time.monotonic() - started < 3:
        frame = source.read(0.1)
        if frame is not None:
            frames.append(frame)
    assert source.state == SourceState.ENDED
    assert len(frames) == 5 and frames[-1].end_sample == 1600
    assert time.monotonic() - started >= 0.099
    source.close()


def test_bad_truncated_and_empty_wav(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not a WAV")
    source = WavReplaySource(path)
    with pytest.raises(AudioSourceError):
        source.start()
    assert source.state == SourceState.ERROR and source._file is None
    write_wav(path, count=0)
    source.start()
    assert source.read(0.1) is None and source.state == SourceState.ENDED
    write_wav(path)
    path.write_bytes(path.read_bytes()[:-3])
    source.start()
    with pytest.raises(AudioSourceError):
        while source.state == SourceState.RUNNING:
            source.read(0.1)
    assert source.state == SourceState.ERROR and source._file is None
    source.close()
