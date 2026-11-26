"""Catalog, verification and atomic installer boundaries; never real downloads."""

import hashlib
import io
import json
import urllib.request
from types import SimpleNamespace

import pytest

from offline_stt.engines import LocalModelStore, ModelCatalog, ModelError
from offline_stt.engines.install import _download, install_model
from offline_stt.engines.models import ModelFile

pytestmark = pytest.mark.usefixtures("deny_engine_network")


def test_complete_model_is_verified_without_network(model_bundle):
    b = model_bundle
    verified = b.store.verify("base-multilingual")
    assert verified.path == b.directory
    assert verified.spec.revision == "1" * 40
    assert b.store.catalog.license_bytes(verified.spec) == b.license_bytes


@pytest.mark.parametrize(
    "filename",
    ["model.bin", "tokenizer.json", "config.json", "vocabulary.txt", "README.md", "LICENSE.txt"],
)
@pytest.mark.parametrize("mode", ["missing", "corrupt"])
def test_every_required_file_is_checked(model_bundle, filename, mode):
    path = model_bundle.directory / filename
    if mode == "missing":
        path.unlink()
    else:
        data = path.read_bytes()
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    with pytest.raises(ModelError, match=filename):
        model_bundle.store.verify("base-multilingual")


def test_unverified_preprocessor_config_is_rejected(model_bundle):
    (model_bundle.directory / "preprocessor_config.json").write_text("{}")
    with pytest.raises(ModelError, match="Unexpected"):
        model_bundle.store.verify("base-multilingual")


@pytest.mark.parametrize(
    "mutation",
    [
        "traversal",
        "duplicate_id",
        "duplicate_file",
        "floating_ref",
        "english",
        "bad_hash",
        "bool_size",
        "missing_file",
        "no_hu",
        "unknown_field",
        "bad_license",
    ],
)
def test_malformed_catalogs_fail_closed(model_bundle, mutation):
    raw = model_bundle.raw
    model = raw["models"][0]
    if mutation == "traversal":
        model["files"][0]["name"] = "../model.bin"
    elif mutation == "duplicate_id":
        raw["models"].append(model)
    elif mutation == "duplicate_file":
        model["files"].append(model["files"][0])
    elif mutation == "floating_ref":
        model["revision"] = "main"
    elif mutation == "english":
        model["multilingual"] = False
    elif mutation == "bad_hash":
        model["files"][0]["sha256"] = "unknown"
    elif mutation == "bool_size":
        model["files"][0]["size"] = True
    elif mutation == "missing_file":
        model["files"].pop()
    elif mutation == "no_hu":
        model["declared_languages"] = ["en"]
    elif mutation == "unknown_field":
        model["auto_download"] = True
    elif mutation == "bad_license":
        model["license"]["upstream_url"] = "https://example.com/license"
    model_bundle.catalog.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ModelError):
        ModelCatalog.read(model_bundle.catalog)


def test_duplicate_json_keys_and_unknown_models(model_bundle):
    with pytest.raises(ModelError, match="Unknown"):
        model_bundle.store.verify("base.en")
    model_bundle.catalog.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ModelError, match="Duplicate"):
        ModelCatalog.read(model_bundle.catalog)


def test_missing_model_cannot_implicitly_download(model_bundle, tmp_path):
    store = LocalModelStore(model_bundle.catalog, tmp_path / "empty")
    with pytest.raises(ModelError, match="missing"):
        store.verify("base-multilingual")
    with pytest.raises(ModelError, match="explicit"):
        install_model(store, "base-multilingual")
    assert not store.root.exists()


def test_installer_checks_hashes_before_activation_and_is_idempotent(model_bundle, tmp_path):
    b = model_bundle
    store = LocalModelStore(b.catalog, tmp_path / "new-cache")
    requests = []

    def download(url, destination, spec):
        assert "/" + "1" * 40 + "/" in url and "/main/" not in url
        requests.append(spec.name)
        destination.write_bytes(b.assets[spec.name])

    verified = install_model(store, "base-multilingual", allow_network=True, downloader=download)
    assert len(requests) == 5
    assert verified.path == store.root / "base-multilingual"
    assert not list(store.root.glob(".install-*"))
    receipt = json.loads((verified.path / "install-receipt.json").read_text())
    assert receipt["revision"] == "1" * 40 and receipt["mode"] == "explicit-network"
    install_model(store, "base-multilingual", downloader=lambda *a: pytest.fail("redownload"))
    assert len(requests) == 5


def test_corrupt_download_does_not_leave_active_or_partial_model(model_bundle, tmp_path):
    store = LocalModelStore(model_bundle.catalog, tmp_path / "new-cache")

    def download(url, destination, spec):
        destination.write_bytes(b"corrupt")

    with pytest.raises(ModelError):
        install_model(store, "base-multilingual", allow_network=True, downloader=download)
    assert not list(store.root.iterdir())


def test_failed_download_cleans_staging_and_existing_corruption_is_not_overwritten(
    model_bundle, tmp_path
):
    store = LocalModelStore(model_bundle.catalog, tmp_path / "new-cache")

    def download(*args):
        raise OSError("simulated interruption")

    with pytest.raises(ModelError, match="no partial"):
        install_model(store, "base-multilingual", allow_network=True, downloader=download)
    assert not list(store.root.iterdir())
    weight = model_bundle.directory / "model.bin"
    weight.write_bytes(b"user-owned damaged model")
    with pytest.raises(ModelError):
        install_model(
            model_bundle.store,
            "base-multilingual",
            allow_network=True,
            downloader=lambda *a: pytest.fail("must not overwrite"),
        )
    assert weight.read_bytes() == b"user-owned damaged model"


def test_offline_bundle_import_and_license_integrity(model_bundle, tmp_path):
    store = LocalModelStore(model_bundle.catalog, tmp_path / "offline-cache")
    verified = install_model(store, "base-multilingual", source_directory=model_bundle.directory)
    assert verified.spec.model_id == "base-multilingual"
    (model_bundle.catalog.parent / "WHISPER_LICENSE.txt").write_bytes(b"bad license")
    other = LocalModelStore(model_bundle.catalog, tmp_path / "other-cache")
    with pytest.raises(ModelError):
        install_model(other, "base-multilingual", source_directory=model_bundle.directory)
    assert not other.root.exists()


@pytest.mark.parametrize(
    "mode", ["valid", "too_large", "truncated", "bad_hash", "bad_host", "bad_redirect"]
)
def test_network_transport_checks_https_hosts_size_and_hash(tmp_path, monkeypatch, mode):
    data = b"synthetic metadata bytes"
    spec = ModelFile("config.json", len(data), hashlib.sha256(data).hexdigest())
    payload = data
    if mode == "too_large":
        payload += b"extra"
    elif mode == "truncated":
        payload = payload[:-1]
    elif mode == "bad_hash":
        payload = b"x" * len(payload)

    class Response(io.BytesIO):
        def geturl(self):
            return (
                "https://untrusted.invalid/file"
                if mode == "bad_host"
                else "https://cdn-lfs.hf.co/file"
            )

    def opener(redirect):
        def open_request(request, timeout):
            assert request.full_url.startswith("https://huggingface.co/")
            assert "nonce=" in request.full_url and timeout == 60
            if mode == "bad_redirect":
                redirect.redirect_request(
                    request, None, 302, "", {}, "http://untrusted.invalid/file"
                )
            return Response(payload)

        return SimpleNamespace(open=open_request)

    monkeypatch.setattr(urllib.request, "build_opener", opener)
    path = tmp_path / "download.json"
    url = "https://huggingface.co/Systran/faster-whisper-base/resolve/" + "1" * 40 + "/config.json"
    if mode == "valid":
        _download(url, path, spec)
        assert path.read_bytes() == data
    else:
        with pytest.raises(ModelError):
            _download(url, path, spec)


def test_real_catalog_is_pinned_and_license_source_hash_is_valid():
    from pathlib import Path

    catalog = ModelCatalog.read(Path(__file__).resolve().parents[2] / "models/manifest.json")
    assert {m.model_id for m in catalog.models} == {"base-multilingual", "small-multilingual"}
    for spec in catalog.models:
        assert "hu" in spec.declared_languages
        assert catalog.license_bytes(spec)


@pytest.mark.parametrize("mode", ["oversized", "same_size_corrupt"])
def test_offline_import_rejects_bad_source_and_cleans_staging(model_bundle, tmp_path, mode):
    source = model_bundle.directory / "model.bin"
    data = source.read_bytes()
    source.write_bytes(data + b"extra" if mode == "oversized" else b"x" * len(data))
    store = LocalModelStore(model_bundle.catalog, tmp_path / "bad-import")
    with pytest.raises(ModelError):
        install_model(store, "base-multilingual", source_directory=model_bundle.directory)
    assert not list(store.root.iterdir())
    assert source.exists()
