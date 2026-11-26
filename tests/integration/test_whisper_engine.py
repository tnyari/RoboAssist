"""Deterministic offline adapter fixture, including lazy decoder failures."""

import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from offline_stt.audio import AudioFrame
from offline_stt.config import Config
from offline_stt.engines import (
    EngineBufferFull,
    EngineError,
    EngineInputError,
    EngineOptions,
    EngineState,
    FasterWhisperEngine,
    LocalModelStore,
)
from offline_stt.engines.whisper import BackendSegment, WhisperDecoder

pytestmark = pytest.mark.usefixtures("deny_engine_network")


class Decoder:
    device = "cpu"
    compute_type = "int8_float32"
    multilingual = True

    def __init__(self):
        self.calls = []
        self.closed = False
        self.fail_next = False
        self.fail_close = False
        self.bad_timestamps = False

    def decode(self, audio, language, tokens):
        # Generator body: call evidence exists only if fully consumed.
        self.calls.append((audio.copy(), language, tokens))
        if self.fail_next:
            self.fail_next = False
            yield BackendSegment(0, 0.01, "partial before failure")
            raise RuntimeError("lazy decode failed")
        if tokens != 1:
            if self.bad_timestamps:
                yield BackendSegment(float("nan"), 0.02, "invalid")
            else:
                yield BackendSegment(0, len(audio) / 16000 + 1, " Szintetikus teszt.")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("unload failed")


def make_engine(bundle, **options):
    decoder = Decoder()
    factory_calls = []

    def factory(verified, threads):
        factory_calls.append((verified, threads))
        return decoder

    engine = FasterWhisperEngine(
        bundle.store, options=EngineOptions(**options), decoder_factory=factory
    )
    return engine, decoder, factory_calls


def frame(start=0, count=320, value=0.25, source="wav"):
    return AudioFrame(np.full(count, value, dtype="float32"), start, source)


def test_load_warmup_once_push_never_decodes_preview_and_flush(model_bundle):
    engine, decoder, calls = make_engine(model_bundle)
    engine.load()
    engine.load()
    assert len(calls) == 1 and calls[0][1] == 4
    assert len(decoder.calls) == 1 and decoder.calls[0][2] == 1
    assert engine.stats.model_loads == 1 and engine.stats.warmup_calls == 1
    assert engine.stats.decode_calls == 0
    engine.push_audio(frame())
    engine.push_audio(frame(320))
    assert len(decoder.calls) == 1
    preview = engine.preview()
    assert not preview.final and engine.stats.buffered_samples == 640
    assert preview.segments[0].text == " Szintetikus teszt."
    assert preview.segments[0].start_sample == 0 and preview.segments[0].end_sample == 640
    final = engine.flush()
    assert final.final and final.end_sample == 640
    assert engine.stats.buffered_samples == 0 and not engine._buffer.any()
    assert engine.flush().segments == () and engine.stats.decode_calls == 2
    engine.push_audio(frame(640))
    assert engine.flush().segments[0].start_sample == 640
    engine.close()
    engine.close()
    assert decoder.closed and engine.state == EngineState.CLOSED


def test_reset_discards_session_without_reload_or_stale_prompt(model_bundle):
    engine, decoder, calls = make_engine(model_bundle)
    engine.load()
    engine.push_audio(frame(value=0.9))
    engine.reset(start_sample=16000)
    assert not engine._buffer.any() and engine.stats.session_input_samples == 0
    engine.push_audio(frame(16000, value=-0.5))
    result = engine.flush()
    assert result.start_sample == 16000 and result.end_sample == 16320
    assert result.segments[0].start_sample == 16000
    np.testing.assert_array_equal(decoder.calls[-1][0], -0.5)
    assert len(calls) == 1 and engine.stats.warmup_calls == 1
    engine.close()


def test_bounded_buffer_rejects_without_consuming_and_can_retry(model_bundle):
    engine, decoder, _ = make_engine(model_bundle, max_audio_seconds=0.02)
    engine.load()
    engine.push_audio(frame())
    with pytest.raises(EngineBufferFull):
        engine.push_audio(frame(320))
    assert engine.stats.session_input_samples == 320 and engine.state == EngineState.READY
    engine.flush()
    engine.push_audio(frame(320))
    assert engine.flush().end_sample == 640
    assert len(decoder.calls) == 3  # warm-up and two accepted final windows
    engine.close()


def test_clock_and_source_errors_do_not_consume_blocks(model_bundle):
    engine, _, _ = make_engine(model_bundle)
    engine.load()
    with pytest.raises(EngineInputError):
        engine.push_audio(frame(1))
    engine.push_audio(frame())
    with pytest.raises(EngineInputError, match="mix"):
        engine.push_audio(frame(320, source="microphone"))
    assert engine.stats.session_input_samples == 320
    engine.close()


def test_lazy_generator_failure_never_returns_half_result_and_reset_recovers(model_bundle):
    engine, decoder, calls = make_engine(model_bundle)
    engine.load()
    engine.push_audio(frame())
    decoder.fail_next = True
    with pytest.raises(EngineError, match="Decode failed"):
        engine.flush()
    assert engine.state == EngineState.ERROR and not engine._buffer.any()
    with pytest.raises(EngineError):
        engine.preview()
    engine.reset()
    engine.push_audio(frame(value=-0.2))
    assert len(engine.flush().segments) == 1
    assert len(calls) == 1  # No hidden reload or fallback.
    decoder.bad_timestamps = True
    engine.push_audio(frame(320))
    with pytest.raises(EngineError):
        engine.preview()
    engine.close()


@pytest.mark.parametrize("mode", ["wrong_device", "float_fallback", "english", "warmup_failure"])
def test_bad_backend_or_warmup_is_cleaned_up(model_bundle, mode):
    engine, decoder, _ = make_engine(model_bundle)
    if mode == "wrong_device":
        decoder.device = "cuda"
    elif mode == "float_fallback":
        decoder.compute_type = "float32"
    elif mode == "english":
        decoder.multilingual = False
    else:
        decoder.fail_next = True
    with pytest.raises(EngineError, match="load failed"):
        engine.load()
    assert decoder.closed and engine.state == EngineState.ERROR
    assert engine._decoder is None
    engine.reset()
    assert engine.state == EngineState.UNLOADED
    engine.close()


def test_corrupt_model_never_reaches_sdk_and_close_errors_are_visible(model_bundle):
    engine, decoder, calls = make_engine(model_bundle)
    (model_bundle.directory / "tokenizer.json").write_bytes(b"bad")
    with pytest.raises(EngineError):
        engine.load()
    assert calls == []
    model_bundle.directory.joinpath("tokenizer.json").write_bytes(
        model_bundle.assets["tokenizer.json"]
    )
    engine.reset()
    engine.load()
    decoder.fail_close = True
    with pytest.raises(EngineError, match="unload"):
        engine.close()
    assert engine.state == EngineState.CLOSED and engine._decoder is None
    assert not engine._buffer.any()
    with pytest.raises(EngineError):
        engine.reset()


def test_config_mapping_and_calls_before_load_are_explicit(model_bundle):
    engine = FasterWhisperEngine.from_config(Config(), model_bundle.store)
    assert engine.options.language == "hu" and engine.options.max_audio_seconds == 12
    with pytest.raises(EngineError):
        engine.push_audio(frame())
    engine.close()
    with pytest.raises(EngineError):
        engine.load()


def test_real_sdk_boundary_uses_local_directory_cpu_int8_and_fixed_decode_options(
    model_bundle, monkeypatch
):
    constructed = []
    transcribed = []
    unloaded = []

    class Model:
        def __init__(self, path, **kwargs):
            constructed.append((path, kwargs))
            self.model = SimpleNamespace(
                device="cpu",
                compute_type="int8_float32",
                is_multilingual=True,
                unload_model=lambda: unloaded.append(True),
            )

        def transcribe(self, audio, **kwargs):
            transcribed.append((audio, kwargs))
            return iter([SimpleNamespace(start=0.0, end=0.02, text="fixture")]), object()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    decoder = WhisperDecoder(model_bundle.store.verify("base-multilingual"), 2)
    assert list(decoder.decode(np.zeros(320, dtype="float32"), "hu", 16))[0].text == "fixture"
    assert constructed[0][0] == str(model_bundle.directory)
    assert constructed[0][1] == {
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 2,
        "num_workers": 1,
        "local_files_only": True,
    }
    kwargs = transcribed[0][1]
    assert kwargs["language"] == "hu" and kwargs["temperature"] == 0 and kwargs["beam_size"] == 1
    assert kwargs["condition_on_previous_text"] is False and kwargs["vad_filter"] is False
    decoder.close()
    assert unloaded == [True]


def test_model_verify_cli_uses_no_weights_backend_or_network(model_bundle):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "offline_stt.engines",
            "--catalog",
            str(model_bundle.catalog),
            "--root",
            str(model_bundle.store.root),
            "verify",
            "base-multilingual",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["network_used"] is False
    missing = LocalModelStore(model_bundle.catalog, model_bundle.store.root / "empty")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "offline_stt.engines",
            "--catalog",
            str(model_bundle.catalog),
            "--root",
            str(missing.root),
            "install",
            "base-multilingual",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2 and "allow-network" in result.stderr
    assert not missing.root.exists()
