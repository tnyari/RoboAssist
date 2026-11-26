"""Schema, safe defaults and configuration boundary failures."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from offline_stt.config import Config, ConfigError, EngineConfig, PrivacyConfig, load_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = (ROOT / "configs/default.toml").read_text(encoding="utf-8")


def test_sample_matches_safe_defaults():
    config = load_config(ROOT / "configs/default.toml")
    assert config == Config()
    assert config.application.language == "hu"
    assert config.application.offline and not config.application.telemetry
    assert config.engine.device == "cpu" and config.engine.compute_type == "int8"
    assert not config.engine.allow_automatic_download
    assert not config.privacy.save_audio and not config.privacy.save_transcript
    with pytest.raises(FrozenInstanceError):
        config.engine.device = "cuda"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("schema_version = 1", "schema_version = 2", "schema_version"),
        ("schema_version = 1", "schema_version = true", "schema_version"),
        ('language = "hu"', 'language = ""', "application.language"),
        ("offline = true", "offline = false", "application.offline"),
        ("telemetry = false", "telemetry = true", "application.telemetry"),
        ("channels = 1", "channels = true", "audio.channels"),
        ("channels = 1", "channels = 2", "audio.channels"),
        ("sample_rate_hz = 16000", "sample_rate_hz = 48000", "audio.sample_rate_hz"),
        ("frame_ms = 20", "frame_ms = 0", "audio.frame_ms"),
        ('backend = "faster-whisper"', 'backend = "cloud"', "engine.backend"),
        ('model = "base-multilingual"', 'model = "  "', "engine.model"),
        ('device = "cpu"', 'device = "cuda"', "engine.device"),
        ('compute_type = "int8"', 'compute_type = "float16"', "engine.compute_type"),
        ("allow_automatic_download = false", "allow_automatic_download = true", "download"),
        ("pre_roll_ms = 250", "pre_roll_ms = -1", "vad.pre_roll_ms"),
        ("pre_roll_ms = 250", "pre_roll_ms = 12000", "vad.pre_roll_ms"),
        ("end_silence_ms = 500", "end_silence_ms = 0", "vad.end_silence_ms"),
        ("end_silence_ms = 500", "end_silence_ms = 12000", "vad.end_silence_ms"),
        ("max_segment_ms = 12000", "max_segment_ms = 60001", "vad.max_segment_ms"),
        ("save_audio = false", 'save_audio = "false"', "privacy.save_audio"),
        ("export_requires_user_action = true", "export_requires_user_action = false", "export"),
        ('device = "cpu"', 'devcie = "cpu"', "hiányzó"),
        ("telemetry = false", "telemetry = false\nunknown = 1", "ismeretlen"),
        ("schema_version = 1", "schema_version = 1\nextra = 1", "ismeretlen"),
        ("[audio]", "[unknown]", "hiányzó"),
        ("schema_version = 1", "schema_version = [", "nem olvasható"),
    ],
)
def test_rejects_invalid_file(tmp_path, old, new, message):
    path = tmp_path / "config.toml"
    path.write_text(DEFAULT.replace(old, new), encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_missing_file_is_actionable(tmp_path):
    with pytest.raises(ConfigError, match="nem olvasható"):
        load_config(tmp_path / "missing.toml")


def test_wrong_section_type(tmp_path):
    path = tmp_path / "config.toml"
    # Replacing a complete table by a scalar must not leak a TypeError.
    text = DEFAULT.replace('[application]\nlanguage = "hu"\noffline = true\ntelemetry = false', "")
    path.write_text(
        text.replace("schema_version = 1", "schema_version = 1\napplication = 1"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="application"):
        load_config(path)


def test_direct_construction_validated_and_explicit_saving_allowed():
    with pytest.raises(ConfigError, match="engine.device"):
        Config(engine=EngineConfig(device="cuda"))
    config = replace(Config(), privacy=PrivacyConfig(save_audio=True, save_transcript=True))
    assert config.privacy.save_audio and config.privacy.export_requires_user_action
