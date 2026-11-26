"""Synthetic engine assets only: no real weights or private audio in CI."""

import hashlib
import json
import os
import socket
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from offline_stt.engines import LocalModelStore


@pytest.fixture
def deny_engine_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Unexpected network access in offline engine test")

    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def model_bundle(tmp_path):
    assets = {
        "model.bin": b"synthetic fake weights, never sent to CTranslate2",
        "config.json": b'{"test_fixture":true}',
        "tokenizer.json": b'{"test_fixture":true}',
        "vocabulary.txt": b"synthetic\n",
        "README.md": b"synthetic fixture, not a real model card\n",
    }
    license_bytes = b"synthetic fixture license bytes, not an upstream license\n"
    catalog_path = tmp_path / "manifest.json"
    (tmp_path / "WHISPER_LICENSE.txt").write_bytes(license_bytes)
    raw = {
        "schema_version": 1,
        "status": "configured",
        "models": [
            {
                "id": "base-multilingual",
                "repository": "Systran/faster-whisper-base",
                "revision": "1" * 40,
                "multilingual": True,
                "declared_languages": ["hu", "en"],
                "files": [
                    {"name": n, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                    for n, b in assets.items()
                ],
                "license": {
                    "spdx": "MIT",
                    "upstream_url": "https://github.com/openai/whisper/blob/"
                    + "2" * 40
                    + "/LICENSE",
                    "model_card_url": "https://huggingface.co/Systran/faster-whisper-base/blob/"
                    + "1" * 40
                    + "/README.md",
                    "text_file": "WHISPER_LICENSE.txt",
                    "size": len(license_bytes),
                    "sha256": hashlib.sha256(license_bytes).hexdigest(),
                },
            }
        ],
    }
    catalog_path.write_text(json.dumps(raw), encoding="utf-8")
    root = tmp_path / "installed"
    model_dir = root / "base-multilingual"
    model_dir.mkdir(parents=True)
    for name, data in assets.items():
        (model_dir / name).write_bytes(data)
    (model_dir / "LICENSE.txt").write_bytes(license_bytes)
    return SimpleNamespace(
        store=LocalModelStore(catalog_path, root),
        directory=model_dir,
        catalog=catalog_path,
        raw=raw,
        assets=assets,
        license_bytes=license_bytes,
    )
