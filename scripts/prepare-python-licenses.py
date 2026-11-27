"""Copy license texts and metadata from the locked Python build environment."""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import shutil
import ssl
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK_PATH = REPO_ROOT / "third_party_licenses" / "python-runtime" / "runtime-lock.json"
OPENSSL_LICENSE_SOURCE = (
    REPO_ROOT / "third_party_licenses" / "python-runtime" / "openssl-3.5.9" / "LICENSE.txt"
)

LICENSE_NAMES = re.compile(
    r"^(license|licence|copying|notice|copyright|thirdpartynotices)([-_.].*)?$",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified_runtime_file(
    python_root: Path, relative_path: str, expected: dict[str, object]
) -> dict[str, object]:
    source = python_root / relative_path
    if not source.is_file():
        raise SystemExit(f"Locked Python runtime file is missing: {source}")
    actual_size = source.stat().st_size
    actual_hash = sha256(source)
    if actual_size != expected["size"] or actual_hash != expected["sha256"]:
        raise SystemExit(f"Locked Python runtime file changed: {source}")
    return {
        "path": relative_path.replace("\\", "/"),
        "size": actual_size,
        "sha256": actual_hash,
    }


def prepare(
    site_packages: Path,
    output: Path,
    python_root: Path,
    *,
    runtime_lock_path: Path = RUNTIME_LOCK_PATH,
    openssl_license_source: Path = OPENSSL_LICENSE_SOURCE,
    running_python_version: str | None = None,
    running_openssl_version: str | None = None,
) -> dict[str, object]:
    project_root = REPO_ROOT
    site_packages = site_packages.resolve()
    output = output.resolve()
    python_root = python_root.resolve()
    if not site_packages.is_dir():
        raise SystemExit(f"Python site-packages directory does not exist: {site_packages}")
    if not python_root.is_dir():
        raise SystemExit(f"Python runtime directory does not exist: {python_root}")
    if output in {project_root, output.parent} or not output.is_relative_to(project_root):
        raise SystemExit(f"License output must stay inside the repository: {output}")

    try:
        runtime_lock = json.loads(runtime_lock_path.read_text(encoding="utf-8"))
        python_lock = runtime_lock["python"]
        openssl_lock = runtime_lock["openssl"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(f"Python runtime lock is invalid: {runtime_lock_path}") from exc

    expected_python_version = str(python_lock["version"])
    if running_python_version is None:
        running_python_version = ".".join(str(part) for part in sys.version_info[:3])
    if running_python_version != expected_python_version:
        raise SystemExit(f"Expected Python {expected_python_version}, got {running_python_version}")
    if (python_root / "python.exe").is_file() is False:
        raise SystemExit(f"Python executable is missing from runtime directory: {python_root}")

    build_marker = (python_root / "BUILD").read_text(encoding="utf-8").strip()
    if build_marker != str(python_lock["build_marker"]):
        raise SystemExit(
            f"Expected python-build-standalone build {python_lock['build_marker']}, "
            f"got {build_marker or '(empty BUILD marker)'}"
        )

    python_license = python_root / str(python_lock["license_path"])
    python_license_hash = sha256(python_license) if python_license.is_file() else None
    if python_license_hash != python_lock["license_sha256"]:
        raise SystemExit(f"Locked CPython license is missing or changed: {python_license}")
    python_dll = _verified_runtime_file(
        python_root, str(python_lock["runtime_dll"]["path"]), python_lock["runtime_dll"]
    )

    expected_openssl_version = str(openssl_lock["version"])
    if running_openssl_version is None:
        match = re.match(r"^OpenSSL\s+(\d+\.\d+\.\d+)", ssl.OPENSSL_VERSION)
        if match is None:
            raise SystemExit(f"Cannot identify runtime OpenSSL version: {ssl.OPENSSL_VERSION}")
        running_openssl_version = match.group(1)
    if running_openssl_version != expected_openssl_version:
        raise SystemExit(
            f"Expected runtime OpenSSL {expected_openssl_version}, got {running_openssl_version}"
        )

    openssl_license_source = openssl_license_source.resolve()
    if (
        not openssl_license_source.is_file()
        or sha256(openssl_license_source) != (openssl_lock["license_sha256"])
    ):
        raise SystemExit(f"Locked OpenSSL license is missing or changed: {openssl_license_source}")

    runtime_dlls = [
        _verified_runtime_file(python_root, str(item["path"]), item)
        for item in openssl_lock["runtime_dlls"]
    ]

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    runtime_output = output / "python-runtime"
    openssl_license_relative = Path("python-runtime") / "openssl-3.5.9" / "LICENSE.txt"
    python_license_relative = Path("python-runtime") / "CPython-LICENSE.txt"
    (runtime_output / "openssl-3.5.9").mkdir(parents=True)
    shutil.copy2(python_license, output / python_license_relative)
    shutil.copy2(openssl_license_source, output / openssl_license_relative)
    runtime_record = {
        "scope": "CPython interpreter and OpenSSL DLLs bundled from the locked Python runtime",
        "python": {
            "implementation": python_lock["implementation"],
            "version": expected_python_version,
            "provider": python_lock["provider"],
            "provider_release": python_lock["provider_release"],
            "installed_by": python_lock["installed_by"],
            "build_marker": build_marker,
            "source_url": python_lock["source_url"],
            "distribution_artifact": python_lock["distribution_artifact"],
            "source_archives": python_lock["source_archives"],
            "runtime_dll": {
                **python_dll,
                "package_path": python_lock["runtime_dll"]["package_path"],
            },
            "license": {
                "expression": python_lock["license_expression"],
                "path": python_license_relative.as_posix(),
                "sha256": python_license_hash,
            },
        },
        "openssl": {
            "version": expected_openssl_version,
            "license_expression": openssl_lock["license_expression"],
            "source_url": openssl_lock["source_url"],
            "source_archive": openssl_lock["source_archive"],
            "license_source_url": openssl_lock["license_source_url"],
            "license_path": openssl_license_relative.as_posix(),
            "license_sha256": openssl_lock["license_sha256"],
            "runtime_dlls": runtime_dlls,
        },
    }
    (output / "python-runtime.json").write_text(
        json.dumps(runtime_record, indent=2) + "\n", encoding="utf-8"
    )

    records: list[dict[str, object]] = []
    supplemental_root = project_root / "third_party_licenses" / "python"
    for metadata_dir in sorted(site_packages.glob("*.dist-info"), key=lambda p: p.name.casefold()):
        metadata = metadata_dir / "METADATA"
        if not metadata.is_file():
            continue
        headers = email.message_from_bytes(metadata.read_bytes())
        name = headers.get("Name") or metadata_dir.name
        version = headers.get("Version") or "unknown"
        slug = re.sub(r"[^A-Za-z0-9_.+-]", "_", f"{name}-{version}")
        destination = output / slug
        files: list[dict[str, str]] = []
        for source in metadata_dir.rglob("*"):
            if not source.is_file() or source == metadata:
                continue
            if not source.relative_to(metadata_dir).parts[0].lower() == "licenses":
                if not LICENSE_NAMES.match(source.name):
                    continue
            relative = source.relative_to(metadata_dir)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            files.append({"path": str(relative).replace("\\", "/"), "sha256": sha256(source)})

        top_level_file = metadata_dir / "top_level.txt"
        if top_level_file.is_file():
            for top_level in top_level_file.read_text(encoding="utf-8").splitlines():
                package_root = site_packages / top_level.strip()
                if not package_root.is_dir():
                    continue
                for source in package_root.iterdir():
                    if not source.is_file() or not LICENSE_NAMES.match(source.name):
                        continue
                    relative = Path("package-level") / source.name
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    files.append(
                        {"path": str(relative).replace("\\", "/"), "sha256": sha256(source)}
                    )

        supplemental = supplemental_root / slug
        supplemental_files: list[dict[str, str]] = []
        if supplemental.is_dir():
            for source in supplemental.rglob("*"):
                if not source.is_file():
                    continue
                relative = Path("supplemental") / source.relative_to(supplemental)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                supplemental_files.append(
                    {"path": str(relative).replace("\\", "/"), "sha256": sha256(source)}
                )

        license_expression = headers.get("License-Expression")
        license_text = headers.get("License")
        project_urls = headers.get_all("Project-URL") or []
        package_note = destination / "PACKAGE-METADATA.txt"
        destination.mkdir(parents=True, exist_ok=True)
        package_note.write_text(
            f"Name: {name}\nVersion: {version}\n"
            f"License-Expression: {license_expression or '(not declared)'}\n"
            f"License: {license_text or '(not declared)'}\n"
            + "".join(f"Project-URL: {url}\n" for url in project_urls),
            encoding="utf-8",
        )
        records.append(
            {
                "name": name,
                "version": version,
                "license_expression": license_expression,
                "license": license_text,
                "license_files": files + supplemental_files,
                "license_text_copied": bool(files or supplemental_files),
                "metadata": str(package_note.relative_to(output)).replace("\\", "/"),
            }
        )

    manifest = {
        "scope": (
            "all installed distributions in the locked Windows x64 Python build environment; "
            "includes build tools"
        ),
        "package_count": len(records),
        "python_runtime": runtime_record,
        "packages_without_distributed_license_text": [
            f"{item['name']}=={item['version']}"
            for item in records
            if not item["license_text_copied"]
        ],
        "packages": records,
    }
    sources = supplemental_root / "SOURCES.md"
    if sources.is_file():
        shutil.copy2(sources, output / "SUPPLEMENTAL-SOURCES.md")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--python-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.site_packages, args.output, args.python_root)
    missing = manifest["packages_without_distributed_license_text"]
    print(
        f"Copied license files for {manifest['package_count']} Python distributions; "
        f"{len(missing)} distribution(s) did not provide a separate license file."
    )
    if missing:
        print("Metadata-only entries: " + ", ".join(str(item) for item in missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
