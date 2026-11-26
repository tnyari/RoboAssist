"""Strict, immutable configuration without engine, capture or UI imports."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, TypeVar


class ConfigError(ValueError):
    """A configuration file is missing, malformed or unsafe."""


@dataclass(frozen=True)
class ApplicationConfig:
    language: str = "hu"
    offline: bool = True
    telemetry: bool = False


@dataclass(frozen=True)
class AudioConfig:
    sample_rate_hz: int = 16000
    channels: int = 1
    frame_ms: int = 20


@dataclass(frozen=True)
class EngineConfig:
    backend: str = "faster-whisper"
    model: str = "base-multilingual"
    device: str = "cpu"
    compute_type: str = "int8"
    allow_automatic_download: bool = False


@dataclass(frozen=True)
class VadConfig:
    pre_roll_ms: int = 250
    end_silence_ms: int = 500
    max_segment_ms: int = 12000


@dataclass(frozen=True)
class PrivacyConfig:
    save_audio: bool = False
    save_transcript: bool = False
    export_requires_user_action: bool = True


@dataclass(frozen=True)
class Config:
    schema_version: int = 1
    application: ApplicationConfig = ApplicationConfig()
    audio: AudioConfig = AudioConfig()
    engine: EngineConfig = EngineConfig()
    vad: VadConfig = VadConfig()
    privacy: PrivacyConfig = PrivacyConfig()

    def __post_init__(self) -> None:
        """Validate direct construction as well as file loading."""
        _same_type("schema_version", self.schema_version, int)
        for name, section_type in _SECTIONS.items():
            section = getattr(self, name)
            _same_type(name, section, section_type)
            for field in fields(section_type):
                # The defaults provide actual types despite postponed annotations.
                expected_type = type(getattr(section_type(), field.name))
                _same_type(f"{name}.{field.name}", getattr(section, field.name), expected_type)
        _require(self.schema_version == 1, "schema_version: csak az 1 támogatott")
        _require(
            re.fullmatch(r"[a-z]{2,3}", self.application.language) is not None,
            "application.language: 2–3 kisbetűs nyelvkód szükséges",
        )
        _require(self.application.offline, "application.offline: true szükséges")
        _require(not self.application.telemetry, "application.telemetry: false szükséges")
        _require(self.audio.sample_rate_hz == 16000, "audio.sample_rate_hz: 16000 szükséges")
        _require(self.audio.channels == 1, "audio.channels: 1 (mono) szükséges")
        _require(self.audio.frame_ms in (10, 20, 30), "audio.frame_ms: 10, 20 vagy 30 szükséges")
        _require(
            self.engine.backend == "faster-whisper",
            "engine.backend: csak a faster-whisper támogatott",
        )
        _require(bool(self.engine.model.strip()), "engine.model: nem lehet üres")
        _require(self.engine.device == "cpu", "engine.device: cpu szükséges")
        _require(self.engine.compute_type == "int8", "engine.compute_type: int8 szükséges")
        _require(
            not self.engine.allow_automatic_download,
            "engine.allow_automatic_download: false szükséges",
        )
        _require(
            1 <= self.vad.max_segment_ms <= 60000,
            "vad.max_segment_ms: 1–60000 szükséges",
        )
        _require(
            0 <= self.vad.pre_roll_ms < self.vad.max_segment_ms,
            "vad.pre_roll_ms: 0 és max_segment_ms közötti érték szükséges (felső határ nélkül)",
        )
        _require(
            0 < self.vad.end_silence_ms < self.vad.max_segment_ms,
            "vad.end_silence_ms: pozitív, max_segment_ms alatti érték szükséges",
        )
        _require(
            self.privacy.export_requires_user_action,
            "privacy.export_requires_user_action: true szükséges",
        )


_SECTIONS = {
    "application": ApplicationConfig,
    "audio": AudioConfig,
    "engine": EngineConfig,
    "vad": VadConfig,
    "privacy": PrivacyConfig,
}
_Section = TypeVar(
    "_Section", ApplicationConfig, AudioConfig, EngineConfig, VadConfig, PrivacyConfig
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _same_type(name: str, value: object, expected: type[Any]) -> None:
    # bool is a subclass of int; TOML true must never pass integer validation.
    _require(type(value) is expected, f"{name}: {expected.__name__} típus szükséges")


def _keys(name: str, data: dict[str, Any], expected: set[str]) -> None:
    missing = expected - data.keys()
    unknown = data.keys() - expected
    _require(not missing, f"{name}: hiányzó mezők: {', '.join(sorted(missing))}")
    _require(not unknown, f"{name}: ismeretlen mezők: {', '.join(sorted(unknown))}")


def _section(data: dict[str, Any], name: str, cls: type[_Section]) -> _Section:
    raw = data[name]
    _same_type(name, raw, dict)
    _keys(name, raw, {field.name for field in fields(cls)})
    return cls(**raw)


def load_config(path: str | Path) -> Config:
    """Load a complete schema-v1 TOML file; never write files or fetch models.

    An explicit path keeps configuration independent of the working directory or
    editable installation. No silent defaults are applied to incomplete files.
    Model availability is checked by the future local engine adapter (#5).
    """
    try:
        with Path(path).open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"A konfiguráció nem olvasható: {path}: {exc}") from exc

    _keys("config", data, {"schema_version", *_SECTIONS})
    return Config(
        schema_version=data["schema_version"],
        application=_section(data, "application", ApplicationConfig),
        audio=_section(data, "audio", AudioConfig),
        engine=_section(data, "engine", EngineConfig),
        vad=_section(data, "vad", VadConfig),
        privacy=_section(data, "privacy", PrivacyConfig),
    )
