"""Explicit installer only. The runtime engine never imports this module."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from offline_stt.engines.models import LocalModelStore, ModelError, ModelFile, VerifiedModel

Downloader = Callable[[str, Path, ModelFile], None]
logger = logging.getLogger(__name__)


def _copy_checked(stream: BinaryIO, destination: Path, spec: ModelFile) -> None:
    digest = hashlib.sha256()
    size = 0
    with destination.open("xb") as output:
        while block := stream.read(min(1024 * 1024, spec.size - size + 1)):
            size += len(block)
            if size > spec.size:
                raise ModelError(f"Source exceeds the pinned file size: {spec.name}")
            digest.update(block)
            output.write(block)
    if size != spec.size or digest.hexdigest() != spec.sha256:
        raise ModelError(f"Copied model size/SHA-256 mismatch: {spec.name}")


def _download(url: str, destination: Path, spec: ModelFile) -> None:
    # Network dependencies are deliberately confined to the explicit installer.
    import urllib.request
    from typing import Any
    from urllib.parse import urlsplit

    def trusted(candidate: str) -> bool:
        parsed = urlsplit(candidate)
        host = parsed.hostname or ""
        return parsed.scheme == "https" and (
            host == "huggingface.co"
            or host.endswith(".huggingface.co")
            or host == "hf.co"
            or host.endswith(".hf.co")
        )

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self,
            req: urllib.request.Request,
            fp: Any,
            code: int,
            msg: str,
            headers: Any,
            newurl: str,
        ) -> urllib.request.Request | None:
            if not trusted(newurl):
                raise ModelError("Model download redirected outside the approved HTTPS hosts")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    if not trusted(url):
        raise ModelError("Unsupported model source")
    request = urllib.request.Request(
        url + "?download=true&nonce=" + uuid.uuid4().hex,
        headers={"User-Agent": "RoboAssist-model-installer/0.1", "Accept-Encoding": "identity"},
    )
    opener = urllib.request.build_opener(Redirect())
    with opener.open(request, timeout=60) as response:
        if not trusted(response.geturl()):
            raise ModelError("Unapproved final model host")
        _copy_checked(response, destination, spec)


def install_model(
    store: LocalModelStore,
    model_id: str,
    *,
    allow_network: bool = False,
    source_directory: str | Path | None = None,
    downloader: Downloader | None = None,
) -> VerifiedModel:
    """Install into a fresh directory; never overwrite an existing/corrupt model.

    Local bundle import needs no network grant. An existing model is verified and
    returned. A failed staging directory is removed only inside the chosen root.
    """
    spec = store.catalog.get(model_id)
    target = store.root / spec.model_id
    if target.exists() or target.is_symlink():
        return store.verify(model_id)
    if source_directory is None and not allow_network:
        raise ModelError("Model download requires explicit --allow-network consent")
    if source_directory is not None and allow_network:
        raise ModelError("Choose local import or explicit network installation, not both")
    license_data = store.catalog.license_bytes(spec)
    store.root.mkdir(parents=True, exist_ok=True)
    required = sum(f.size for f in spec.installed_files)
    if shutil.disk_usage(store.root).free < required + 32 * 1024**2:
        raise ModelError("Not enough free space for the pinned model staging directory")
    stage = store.root / (".install-" + uuid.uuid4().hex)
    stage.mkdir()
    if stage.resolve().parent != store.root or stage.is_symlink():
        raise ModelError("Staging path left the model root")
    try:
        for file in spec.files:
            destination = stage / file.name
            if source_directory is not None:
                source = Path(source_directory).resolve() / file.name
                if (
                    source.is_symlink()
                    or source.resolve().parent != Path(source_directory).resolve()
                ):
                    raise ModelError("Local import file leaves its source directory")
                if not source.is_file() or source.stat().st_size != file.size:
                    raise ModelError(f"Local import source size mismatch: {file.name}")
                with source.open("rb") as stream:
                    _copy_checked(stream, destination, file)
            else:
                logger.info("Downloading %s/%s (%d bytes)", spec.model_id, file.name, file.size)
                (downloader or _download)(spec.source_url(file.name), destination, file)
        (stage / "LICENSE.txt").write_bytes(license_data)
        store.verify_directory(stage, spec)
        receipt = {
            "schema_version": 1,
            "model_id": spec.model_id,
            "repository": spec.repository,
            "revision": spec.revision,
            "license": spec.license.spdx,
            "mode": "local-import" if source_directory is not None else "explicit-network",
            "files": [
                {"name": f.name, "size": f.size, "sha256": f.sha256} for f in spec.installed_files
            ],
        }
        (stage / "install-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        # The validated source and target are direct children of the configured root.
        if stage.resolve().parent != store.root or target.resolve().parent != store.root:
            raise ModelError("Model promotion path leaves its configured root")
        stage.rename(target)
        return store.verify(model_id)
    except (OSError, ValueError) as exc:
        raise ModelError(
            "Explicit model installation failed; no partial model was activated"
        ) from exc
    finally:
        if stage.exists():
            if stage.is_symlink() or stage.resolve().parent != store.root:
                raise ModelError("Refusing unsafe staging cleanup")
            if not stage.name.startswith(".install-"):
                raise ModelError("Refusing cleanup outside the staging namespace")
            shutil.rmtree(stage)
