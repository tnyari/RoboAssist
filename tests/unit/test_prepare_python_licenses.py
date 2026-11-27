import hashlib
import json
import runpy
import shutil
import tempfile
from pathlib import Path

import pytest

PREPARE = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts" / "prepare-python-licenses.py")
)["prepare"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def scratch_directory():
    parent = Path(__file__).resolve().parent
    root = Path(tempfile.mkdtemp(prefix=".python-license-test-", dir=parent))
    try:
        yield root
    finally:
        shutil.rmtree(root)


def _runtime_fixture(root: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    python_root = root / "python"
    python_root.mkdir()
    (python_root / "python.exe").write_bytes(b"fixture executable")
    (python_root / "BUILD").write_text("fixture-build\n", encoding="utf-8")
    python_license = python_root / "LICENSE.txt"
    python_license.write_text("fixture CPython license\n", encoding="utf-8")
    python_dll_path = python_root / "python311.dll"
    python_dll_path.write_bytes(b"fixture python DLL")
    dll_dir = python_root / "DLLs"
    dll_dir.mkdir()
    dlls = []
    for name, contents in (("libcrypto-3-x64.dll", b"crypto"), ("libssl-3-x64.dll", b"ssl")):
        dll = dll_dir / name
        dll.write_bytes(contents)
        dlls.append({"path": f"DLLs/{name}", "size": dll.stat().st_size, "sha256": _sha256(dll)})

    openssl_license = root / "openssl" / "LICENSE.txt"
    openssl_license.parent.mkdir()
    openssl_license.write_text("fixture Apache license\n", encoding="utf-8")
    upstream_sources_path = "_internal/licenses/upstream-sources/"
    lock = {
        "python": {
            "version": "3.11.18",
            "implementation": "CPython",
            "provider": "fixture provider",
            "provider_release": "fixture-release",
            "installed_by": "fixture installer",
            "build_marker": "fixture-build",
            "source_url": "https://example.invalid/python",
            "source_archives": [
                {
                    "name": "fixture-python-source.tar.gz",
                    "url": "https://example.invalid/python-source.tar.gz",
                    "size": 1,
                    "sha256": "1" * 64,
                    "package_path": upstream_sources_path + "fixture-python-source.tar.gz",
                }
            ],
            "distribution_artifact": {
                "name": "fixture-python.tar.gz",
                "url": "https://example.invalid/python.tar.gz",
                "size": 1,
                "sha256": "0" * 64,
            },
            "license_expression": "PSF-2.0",
            "license_path": "LICENSE.txt",
            "license_sha256": _sha256(python_license),
            "runtime_dll": {
                "path": "python311.dll",
                "size": python_dll_path.stat().st_size,
                "sha256": _sha256(python_dll_path),
                "package_path": "_internal/python311.dll",
            },
        },
        "openssl": {
            "version": "3.5.9",
            "license_expression": "Apache-2.0",
            "source_url": "https://example.invalid/openssl.tar.gz",
            "source_archive": {
                "name": "fixture-openssl-source.tar.gz",
                "url": "https://example.invalid/openssl-source.tar.gz",
                "size": 1,
                "sha256": "2" * 64,
                "package_path": upstream_sources_path + "fixture-openssl-source.tar.gz",
            },
            "license_source_url": "https://example.invalid/openssl-license",
            "license_sha256": _sha256(openssl_license),
            "runtime_dlls": dlls,
        },
    }
    lock_path = root / "runtime-lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    return python_root, openssl_license, lock_path, lock


def test_prepare_copies_runtime_licenses_and_records_locked_dlls(scratch_directory, monkeypatch):
    root = scratch_directory
    python_root, openssl_license, lock_path, lock = _runtime_fixture(root)
    site_packages = root / "site-packages"
    site_packages.mkdir()
    monkeypatch.setitem(PREPARE.__globals__, "REPO_ROOT", root)
    output = root / ".tools" / "license-bundle"

    manifest = PREPARE(
        site_packages,
        output,
        python_root,
        runtime_lock_path=lock_path,
        openssl_license_source=openssl_license,
        running_python_version="3.11.18",
        running_openssl_version="3.5.9",
    )

    runtime = manifest["python_runtime"]
    assert runtime["python"]["provider_release"] == "fixture-release"
    assert runtime["python"]["source_archives"] == lock["python"]["source_archives"]
    assert runtime["python"]["runtime_dll"]["sha256"] == lock["python"]["runtime_dll"]["sha256"]
    assert runtime["openssl"]["source_archive"] == lock["openssl"]["source_archive"]
    assert runtime["openssl"]["runtime_dlls"] == lock["openssl"]["runtime_dlls"]
    assert (output / "python-runtime" / "CPython-LICENSE.txt").is_file()
    assert (output / "python-runtime" / "openssl-3.5.9" / "LICENSE.txt").read_bytes() == (
        openssl_license.read_bytes()
    )
    assert json.loads((output / "python-runtime.json").read_text(encoding="utf-8")) == runtime


def test_prepare_rejects_runtime_dll_drift_before_replacing_output(scratch_directory, monkeypatch):
    root = scratch_directory
    python_root, openssl_license, lock_path, _ = _runtime_fixture(root)
    site_packages = root / "site-packages"
    site_packages.mkdir()
    monkeypatch.setitem(PREPARE.__globals__, "REPO_ROOT", root)
    output = root / ".tools" / "license-bundle"
    output.mkdir(parents=True)
    marker = output / "previous-build.txt"
    marker.write_text("keep on validation failure", encoding="utf-8")
    (python_root / "DLLs" / "libssl-3-x64.dll").write_bytes(b"changed dll")

    with pytest.raises(SystemExit, match="Locked Python runtime file changed"):
        PREPARE(
            site_packages,
            output,
            python_root,
            runtime_lock_path=lock_path,
            openssl_license_source=openssl_license,
            running_python_version="3.11.18",
            running_openssl_version="3.5.9",
        )

    assert marker.read_text(encoding="utf-8") == "keep on validation failure"
