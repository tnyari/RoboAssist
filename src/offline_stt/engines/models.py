"""Strict pinned catalog and local-only model validation. No network imports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelError(RuntimeError):
    """Missing, unsupported or corrupt local model/catalog."""


HUB_FILES = frozenset({"model.bin", "config.json", "tokenizer.json", "vocabulary.txt", "README.md"})
REPOSITORIES = {
    "base-multilingual": "Systran/faster-whisper-base",
    "small-multilingual": "Systran/faster-whisper-small",
}


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelError(f"Duplicate catalog key: {key}")
        result[key] = value
    return result


def _keys(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ModelError("Unexpected or missing catalog fields")
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ModelError("Catalog text field is empty or not a string")
    return value


def _hash(value: Any) -> str:
    text = _text(value)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ModelError("Expected a lowercase SHA-256")
    return text


def _size(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 2 * 1024**3:
        raise ModelError("Invalid model file size")
    return value


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ModelLicense:
    spdx: str
    upstream_url: str
    model_card_url: str
    text_file: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    repository: str
    revision: str
    declared_languages: tuple[str, ...]
    files: tuple[ModelFile, ...]
    license: ModelLicense

    @property
    def installed_files(self) -> tuple[ModelFile, ...]:
        return self.files + (ModelFile("LICENSE.txt", self.license.size, self.license.sha256),)

    def source_url(self, filename: str) -> str:
        if filename not in HUB_FILES:
            raise ModelError("Not a supported upstream file")
        return f"https://huggingface.co/{self.repository}/resolve/{self.revision}/{filename}"


@dataclass(frozen=True)
class ModelCatalog:
    path: Path
    models: tuple[ModelSpec, ...]

    @classmethod
    def read(cls, path: str | Path) -> ModelCatalog:
        path = Path(path).resolve()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object)
            root = _keys(raw, {"schema_version", "status", "models"})
            if type(root["schema_version"]) is not int or root["schema_version"] != 1:
                raise ModelError("Unsupported model catalog schema")
            if root["status"] != "configured" or not isinstance(root["models"], list):
                raise ModelError("Model catalog is not configured")
            models = tuple(_parse_model(item) for item in root["models"])
            if not models or len({m.model_id for m in models}) != len(models):
                raise ModelError("Empty catalog or duplicate model identifiers")
            return cls(path, models)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ModelError(f"Model catalog cannot be read: {path}") from exc

    def get(self, model_id: str) -> ModelSpec:
        for model in self.models:
            if model.model_id == model_id:
                return model
        raise ModelError(f"Unknown local model identifier: {model_id}")

    def license_bytes(self, spec: ModelSpec) -> bytes:
        path = self.path.parent / spec.license.text_file
        if path.is_symlink() or path.resolve().parent != self.path.parent:
            raise ModelError("License file leaves the catalog directory")
        _verify_file(path, ModelFile(path.name, spec.license.size, spec.license.sha256))
        return path.read_bytes()


def _parse_model(raw: Any) -> ModelSpec:
    item = _keys(
        raw,
        {"id", "repository", "revision", "multilingual", "declared_languages", "files", "license"},
    )
    model_id = _text(item["id"])
    repository = _text(item["repository"])
    if model_id not in REPOSITORIES or repository != REPOSITORIES[model_id]:
        raise ModelError("Only the pinned multilingual base/small sources are supported")
    revision = _text(item["revision"])
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or item["multilingual"] is not True:
        raise ModelError("Expected an immutable revision and multilingual model")
    languages = item["declared_languages"]
    if (
        not isinstance(languages, list)
        or "hu" not in languages
        or any(not isinstance(s, str) or not re.fullmatch(r"[a-z]{2,3}", s) for s in languages)
    ):
        raise ModelError("Expected upstream-declared languages including hu")
    if not isinstance(item["files"], list):
        raise ModelError("Expected a model file list")
    files = []
    for entry in item["files"]:
        f = _keys(entry, {"name", "size", "sha256"})
        name = _text(f["name"])
        if name not in HUB_FILES:
            raise ModelError("Unexpected model filename")
        files.append(ModelFile(name, _size(f["size"]), _hash(f["sha256"])))
    if len(files) != len(HUB_FILES) or {f.name for f in files} != HUB_FILES:
        raise ModelError("Missing or duplicate required model files")
    lic = _keys(
        item["license"], {"spdx", "upstream_url", "model_card_url", "text_file", "size", "sha256"}
    )
    if lic["spdx"] != "MIT" or lic["text_file"] != "WHISPER_LICENSE.txt":
        raise ModelError("Unsupported model license record")
    upstream = _text(lic["upstream_url"])
    if not re.fullmatch(r"https://github\.com/openai/whisper/blob/[0-9a-f]{40}/LICENSE", upstream):
        raise ModelError("Expected pinned upstream license source")
    card = _text(lic["model_card_url"])
    if card != f"https://huggingface.co/{repository}/blob/{revision}/README.md":
        raise ModelError("Model card must refer to the same immutable revision")
    license_spec = ModelLicense(
        "MIT", upstream, card, "WHISPER_LICENSE.txt", _size(lic["size"]), _hash(lic["sha256"])
    )
    return ModelSpec(model_id, repository, revision, tuple(languages), tuple(files), license_spec)


def _verify_file(path: Path, spec: ModelFile) -> None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size != spec.size:
            raise ModelError(f"Missing or unexpected-size local model file: {spec.name}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != spec.sha256:
            raise ModelError(f"Local model SHA-256 mismatch: {spec.name}")
    except OSError as exc:
        raise ModelError(f"Local model file cannot be read: {spec.name}") from exc


@dataclass(frozen=True)
class VerifiedModel:
    path: Path
    spec: ModelSpec


class LocalModelStore:
    def __init__(self, catalog: str | Path, root: str | Path) -> None:
        self.catalog = ModelCatalog.read(catalog)
        self.root = Path(root).resolve()

    def verify(self, model_id: str) -> VerifiedModel:
        spec = self.catalog.get(model_id)
        directory = self.root / spec.model_id
        if directory.resolve().parent != self.root:
            raise ModelError("Model directory leaves its configured root")
        return self.verify_directory(directory, spec)

    def verify_directory(self, directory: Path, spec: ModelSpec) -> VerifiedModel:
        try:
            if directory.is_symlink() or not directory.is_dir():
                raise ModelError(f"Local model is missing: {spec.model_id}; install it explicitly")
            resolved = directory.resolve()
            expected = {f.name for f in spec.installed_files}
            present = {p.name for p in resolved.iterdir()}
            if present - expected - {"install-receipt.json"}:
                raise ModelError("Unexpected local model files; unverified config is not loaded")
            for file in spec.installed_files:
                path = resolved / file.name
                if path.resolve().parent != resolved:
                    raise ModelError("Model file leaves its directory")
                _verify_file(path, file)
            return VerifiedModel(resolved, spec)
        except OSError as exc:
            raise ModelError(f"Local model directory cannot be read: {spec.model_id}") from exc
