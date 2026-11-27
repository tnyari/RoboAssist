"""Copy license texts and metadata from the locked Python build environment."""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import shutil
from pathlib import Path

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


def prepare(site_packages: Path, output: Path) -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[1]
    site_packages = site_packages.resolve()
    output = output.resolve()
    if not site_packages.is_dir():
        raise SystemExit(f"Python site-packages directory does not exist: {site_packages}")
    if output in {project_root, output.parent} or not output.is_relative_to(project_root):
        raise SystemExit(f"License output must stay inside the repository: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.site_packages, args.output)
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
