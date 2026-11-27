"""Windows-spawn session lifecycle and real WAV reader with synthetic/fake STT."""

import socket
import time
import wave
from dataclasses import dataclass, replace
from threading import current_thread

import numpy as np
import pytest

from offline_stt.audio import AudioFrame
from offline_stt.audio.types import AudioSourceError, SourceState, SourceStats
from offline_stt.config import Config, PipelineConfig, VadConfig
from offline_stt.engines import FasterWhisperEngine, LocalModelStore
from offline_stt.engines.whisper import BackendSegment
from offline_stt.pipeline import PipelineError, Session, SessionState, WavSourceFactory


def deny_network(*args, **kwargs):
    raise AssertionError("No network is permitted in the spawned fixture worker")


class Decoder:
    device = "cpu"
    compute_type = "int8_float32"
    multilingual = True

    def __init__(self, mode):
        self.mode = mode

    def decode(self, audio, language, tokens):
        assert current_thread().name == "STT decoder"
        if tokens == 1:
            return
        if self.mode == "hang":
            time.sleep(30)
        if self.mode == "fail":
            raise RuntimeError("injected decoder error")
        if self.mode == "slow":
            time.sleep(0.3)
        time.sleep(0.005)
        yield BackendSegment(0, len(audio) / 16000, "Szintetikus egy kettő.")

    def close(self):
        if self.mode == "close_fail":
            raise RuntimeError("injected unload error")


@dataclass(frozen=True)
class DecoderFactory:
    mode: str = "normal"

    def __call__(self, verified, threads):
        return Decoder(self.mode)


@dataclass(frozen=True)
class EngineFactory:
    catalog: str
    root: str
    mode: str = "normal"

    def __call__(self):
        socket.getaddrinfo = deny_network
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        return FasterWhisperEngine(
            LocalModelStore(self.catalog, self.root), decoder_factory=DecoderFactory(self.mode)
        )


class Source:
    def __init__(self, mode):
        self.mode = mode
        self.state = SourceState.IDLE
        self.error = None
        self.index = 0

    def start(self):
        assert current_thread().name == "Audio reader"
        self.state = SourceState.RUNNING

    def read(self, timeout=0.05):
        if self.state == SourceState.ENDED:
            return None
        if self.mode == "hang":
            time.sleep(30)
        time.sleep(0.003)
        if self.mode == "fail" and self.index == 40:
            raise AudioSourceError("injected device disconnect")
        if self.mode == "finite" and self.index == 75:
            self.state = SourceState.ENDED
            return None
        # Multiple voice/silence bursts allow final-event backpressure testing.
        value = 0.2 if self.mode != "bursts" or self.index % 35 < 5 else 0
        frame = AudioFrame(np.full(320, value, dtype="float32"), self.index * 320, "microphone")
        self.index += 1
        if self.mode == "bursts" and self.index == 140:
            self.state = SourceState.ENDED
        return frame

    def close(self):
        assert current_thread().name == "Audio reader"
        self.state = SourceState.CLOSED

    @property
    def stats(self):
        return SourceStats(output_frames=self.index)


@dataclass(frozen=True)
class SourceFactory:
    mode: str = "finite"

    def __call__(self):
        return Source(self.mode)


def factory(bundle, mode="normal"):
    return EngineFactory(str(bundle.catalog), str(bundle.store.root), mode)


def config(**overrides):
    return Config(pipeline=replace(PipelineConfig(), partial_interval_ms=100, **overrides))


def until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for session evidence")
        time.sleep(0.01)


def test_generated_wav_replay_runs_vad_engine_events_and_closes_without_exports(
    model_bundle, tmp_path
):
    path = tmp_path / "synthetic.wav"
    tone = 0.2 * np.sin(2 * np.pi * 220 * np.arange(8000) / 16000)
    samples = np.concatenate([tone, np.zeros(9600)])
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(np.rint(samples * 32767).astype("<i2").tobytes())
    before = set(tmp_path.rglob("*"))
    session = Session(config(), WavSourceFactory(str(path)), factory(model_bundle))
    try:
        session_id = session.start()
        assert session.wait(10)
        assert session.state == SessionState.STOPPED and session.error is None
        events = session.drain_events()
        finals = [e for e in events if e.type == "final"]
        assert len(finals) == 1 and finals[0].session_id == session_id
        assert finals[0].source == "wav" and finals[0].audio_start_ms == 0
        assert finals[0].audio_end_ms == 1000  # 500 ms voice + 500 ms endpoint silence
        assert finals[0].text == "Szintetikus egy kettő."
        stats = session.stats
        assert stats.audio_samples == len(samples)
        assert stats.source_started_monotonic_ns is not None
        assert stats.source_started_monotonic_ns > 0
        assert stats.engine_model_loads == stats.engine_warmup_calls == 1
        assert stats.final_decodes == 1 and stats.partial_decodes >= 1
        assert stats.repeated_decode_samples > 0
        assert not session.worker_alive and set(tmp_path.rglob("*")) == before
    finally:
        session.close()
    assert session.state == SessionState.CLOSED and session.drain_events() == ()


def test_stop_start_and_reset_isolate_sessions_and_flush_once(model_bundle):
    session = Session(config(), SourceFactory("infinite"), factory(model_bundle))
    ids = []
    try:
        for _ in range(2):
            ids.append(session.start())
            until(lambda: session.stats.audio_frames >= 20)
            session.stop(timeout=3)
            session.stop(timeout=3)
            assert session.error is None and not session.worker_alive
            events = session.drain_events()
            assert len([e for e in events if e.type == "final"]) == 1
            assert {e.session_id for e in events} == {ids[-1]}
            assert session.stats.engine_model_loads == 1
        session.reset()
        assert session.state == SessionState.IDLE and session.session_id == ""
        assert session.drain_events() == ()
        assert ids[0] != ids[1]
    finally:
        session.close()


@pytest.mark.parametrize("fault", ["device", "decoder", "unload"])
def test_device_decoder_and_cleanup_failures_visible_then_clean_restart(model_bundle, fault):
    source = SourceFactory("fail" if fault == "device" else "finite")
    mode = "fail" if fault == "decoder" else "close_fail" if fault == "unload" else "normal"
    session = Session(config(), source, factory(model_bundle, mode))
    try:
        session.start()
        assert session.wait(10)
        assert session.state == SessionState.ERROR and session.error
        assert not session.worker_alive and not session.drain_events()
        session.source_factory = SourceFactory()
        session.engine_factory = factory(model_bundle)
        session.start()
        assert session.wait(10) and session.error is None
        assert len([e for e in session.drain_events() if e.type == "final"]) == 1
    finally:
        session.close()


@pytest.mark.parametrize("blocked", ["decoder", "source"])
def test_stop_timeout_terminates_blocked_native_work_and_all_capture_threads(model_bundle, blocked):
    session = Session(
        config(),
        SourceFactory("hang" if blocked == "source" else "infinite"),
        factory(model_bundle, "hang" if blocked == "decoder" else "normal"),
    )
    try:
        session.start()
        if blocked == "decoder":
            until(lambda: session.stats.audio_frames >= 20)
        started = time.monotonic()
        with pytest.raises(PipelineError, match="timeout"):
            session.stop(timeout=1)
        assert time.monotonic() - started < 2
        assert not session.worker_alive and session.stats.forced_terminations == 1
        assert session.state == SessionState.ERROR and not session.drain_events()
        session.reset()
        assert session.state == SessionState.IDLE
    finally:
        session.close()


def test_model_load_error_has_no_source_or_stale_events_and_can_restart(model_bundle):
    missing = EngineFactory(str(model_bundle.catalog), str(model_bundle.store.root / "missing"))
    session = Session(config(), SourceFactory(), missing)
    try:
        with pytest.raises(PipelineError, match="load failed"):
            session.start()
        assert not session.worker_alive and session.state == SessionState.ERROR
        session.engine_factory = factory(model_bundle)
        session.start()
        assert session.wait(10) and session.error is None
    finally:
        session.close()


def test_final_event_buffer_overflow_is_visible_and_bounded(model_bundle):
    session = Session(
        config(event_queue_capacity=2), SourceFactory("bursts"), factory(model_bundle)
    )
    try:
        session.start()
        assert session.wait(10)
        assert session.state == SessionState.ERROR and "buffer overflow" in session.error
        assert session.stats.output_final_failures == 1
        assert not session.worker_alive
    finally:
        session.close()


def test_slow_decoder_final_work_overload_is_visible_instead_of_silent_audio_loss(model_bundle):
    settings = Config(
        vad=VadConfig(pre_roll_ms=0, end_silence_ms=100, max_segment_ms=200),
        pipeline=replace(PipelineConfig(), final_queue_capacity=1, partial_interval_ms=100),
    )
    session = Session(settings, SourceFactory(), factory(model_bundle, "slow"))
    try:
        session.start()
        assert session.wait(10)
        assert session.state == SessionState.ERROR and "Final queue overflow" in session.error
        assert session.stats.final_jobs_rejected == 1
        assert session.stats.max_job_backlog <= 2
        assert not session.worker_alive and not session.drain_events()
    finally:
        session.close()


def test_closed_session_rejects_reuse(model_bundle):
    session = Session(Config(vad=VadConfig()), SourceFactory(), factory(model_bundle))
    session.close()
    with pytest.raises(PipelineError, match="closed"):
        session.start()
