"""Stage Qt/PySide license texts from hash-locked upstream source archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = (REPO_ROOT / ".tools").resolve()
OUTPUT_ROOT = (TOOLS_ROOT / "qt-license-bundle").resolve()


@dataclass(frozen=True)
class SourceArchive:
    filename: str
    project: str
    url: str
    sha256: str
    root: str


SOURCES = (
    SourceArchive(
        filename="qtbase-everywhere-src-6.12.0.tar.xz",
        project="qtbase",
        url=(
            "https://download.qt.io/archive/qt/6.12/6.12.0/submodules/"
            "qtbase-everywhere-src-6.12.0.tar.xz"
        ),
        sha256="a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307",
        root="qtbase-everywhere-src-6.12.0",
    ),
    SourceArchive(
        filename="qtsvg-everywhere-src-6.12.0.tar.xz",
        project="qtsvg",
        url=(
            "https://download.qt.io/archive/qt/6.12/6.12.0/submodules/"
            "qtsvg-everywhere-src-6.12.0.tar.xz"
        ),
        sha256="e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331",
        root="qtsvg-everywhere-src-6.12.0",
    ),
    SourceArchive(
        filename="qtimageformats-everywhere-src-6.12.0.tar.xz",
        project="qtimageformats",
        url=(
            "https://download.qt.io/archive/qt/6.12/6.12.0/submodules/"
            "qtimageformats-everywhere-src-6.12.0.tar.xz"
        ),
        sha256="0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762",
        root="qtimageformats-everywhere-src-6.12.0",
    ),
    SourceArchive(
        filename="pyside-setup-v6.12.0.tar.gz",
        project="pyside",
        url="https://github.com/pyside/pyside-setup/archive/refs/tags/v6.12.0.tar.gz",
        sha256="dce2a944b34320e51a0ec8100cb983956399b97dec386f0fbe39e1b52571a336",
        root="pyside-setup-6.12.0",
    ),
)

REQUIRED_SOURCE_PATHS = {
    "qtbase": (
        "LICENSES/LGPL-3.0-only.txt",
        "src/3rdparty/libjpeg/LICENSE",
        "src/3rdparty/libjpeg/ijg-license.txt",
        "src/3rdparty/libjpeg/README.ijg",
        "src/3rdparty/libjpeg/COPYRIGHT.txt",
        "src/3rdparty/libjpeg/qt_attribution.json",
    ),
    "qtsvg": ("LICENSES/LGPL-3.0-only.txt",),
    "qtimageformats": (
        "LICENSES/LGPL-3.0-only.txt",
        "LICENSES/libtiff.txt",
        "src/3rdparty/libtiff/COPYRIGHT",
        "src/3rdparty/libtiff/qt_attribution.json",
        "src/3rdparty/libwebp/COPYING",
        "src/3rdparty/libwebp/qt_attribution.json",
    ),
    "pyside": ("LICENSES/LGPL-3.0-only.txt",),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_license_file(relative_path: PurePosixPath) -> bool:
    parts = relative_path.parts
    if parts and parts[0].casefold() == "licenses":
        return True

    name = relative_path.name.casefold()
    if name == "readme.ijg":
        return True
    text_suffixes = {"", ".html", ".license", ".md", ".rtf", ".txt"}
    has_license_name = bool(
        re.search(r"(^|[._-])(license|copying|notice|copyright)([._-]|$)", name)
    )
    return has_license_name and relative_path.suffix.casefold() in text_suffixes


def should_extract(relative_path: PurePosixPath, source: SourceArchive) -> bool:
    parts = relative_path.parts
    if parts and parts[0].casefold() == "licenses":
        return True
    if (
        relative_path.name.casefold() == "qt_attribution.json"
        and parts
        and parts[0].casefold() == "src"
    ):
        return True
    if relative_path.as_posix() in REQUIRED_SOURCE_PATHS[source.project]:
        return True
    if source.project in {"qtbase", "qtimageformats"}:
        return (
            len(parts) > 2 and parts[:2] == ("src", "3rdparty") and is_license_file(relative_path)
        )
    if source.project == "pyside":
        return (
            len(parts) > 2
            and parts[:2] == ("sources", "pyside6")
            and is_license_file(relative_path)
        )
    return False


def safe_relative_path(member_name: str, source: SourceArchive) -> PurePosixPath:
    path = PurePosixPath(member_name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"Unsafe path in source archive {source.filename}: {member_name}")
    if not path.parts or path.parts[0] != source.root or len(path.parts) < 2:
        raise ValueError(f"Unexpected source root in {source.filename}: {member_name}")
    return PurePosixPath(*path.parts[1:])


def prepare_bundle(source_dir: Path, output: Path) -> dict[str, object]:
    source_dir = source_dir.resolve()
    output = output.resolve()
    if output != OUTPUT_ROOT or not output.is_relative_to(TOOLS_ROOT):
        raise ValueError(f"Output must be the workspace staging directory: {OUTPUT_ROOT}")

    extracted: list[dict[str, object]] = []
    archive_rows: list[dict[str, str]] = []
    staged_files: list[tuple[Path, bytes]] = []

    for source in SOURCES:
        archive_path = source_dir / source.filename
        if not archive_path.is_file():
            raise FileNotFoundError(f"Required Qt/PySide source archive is missing: {archive_path}")
        archive_hash = sha256_bytes(archive_path.read_bytes())
        if archive_hash != source.sha256:
            raise ValueError(f"Source archive hash mismatch for {source.filename}: {archive_hash}")

        archive_rows.append(
            {
                "filename": source.filename,
                "project": source.project,
                "url": source.url,
                "sha256": archive_hash,
            }
        )
        seen_required: set[str] = set()
        with tarfile.open(archive_path, mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                relative = safe_relative_path(member.name, source)
                relative_text = relative.as_posix()
                if relative_text in REQUIRED_SOURCE_PATHS[source.project]:
                    seen_required.add(relative_text)
                if not should_extract(relative, source):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"Could not read license file {member.name}")
                data = stream.read()
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError(f"Unexpectedly large license file: {member.name}")
                destination = Path(source.project) / Path(*relative.parts)
                staged_files.append((destination, data))
                extracted.append(
                    {
                        "project": source.project,
                        "archive": source.filename,
                        "source_path": relative_text,
                        "output_path": destination.as_posix(),
                        "bytes": len(data),
                        "sha256": sha256_bytes(data),
                    }
                )

        missing = set(REQUIRED_SOURCE_PATHS[source.project]) - seen_required
        if missing:
            raise ValueError(
                f"Required license files missing from {source.filename}: {sorted(missing)}"
            )

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for relative, data in staged_files:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    manifest: dict[str, object] = {
        "schema_version": 1,
        "qt_version": "6.12.0",
        "scope": (
            "License and notice files copied from hash-locked upstream Qt/PySide source archives. "
            "This inventory does not prove which third-party code is linked into packaged binaries."
        ),
        "source_archives": archive_rows,
        "files": extracted,
        "source_attribution_documents": [
            {
                "project": row["project"],
                "archive": row["archive"],
                "source_path": row["source_path"],
                "output_path": row["output_path"],
                "sha256": row["sha256"],
                "evidence_limit": (
                    "Upstream source attribution; the vendor binary's build options "
                    "and linked components are not proven."
                ),
            }
            for row in extracted
            if str(row["source_path"]).endswith("qt_attribution.json")
        ],
        "candidate_plugin_notices": [
            {
                "plugin": "qjpeg.dll",
                "source_archive": "qtbase-everywhere-src-6.12.0.tar.xz",
                "source_attribution": "qtbase/src/3rdparty/libjpeg/qt_attribution.json",
                "upstream_component": "libjpeg-turbo 3.2.0",
                "upstream_condition": "Qt says it is used if system libjpeg is not selected.",
                "source_paths": [
                    "src/3rdparty/libjpeg/LICENSE",
                    "src/3rdparty/libjpeg/ijg-license.txt",
                    "src/3rdparty/libjpeg/README.ijg",
                    "src/3rdparty/libjpeg/COPYRIGHT.txt",
                ],
                "evidence_limit": (
                    "Source attribution only; the shipped binary's linkage is unverified."
                ),
            },
            {
                "plugin": "qtiff.dll",
                "source_archive": "qtimageformats-everywhere-src-6.12.0.tar.xz",
                "source_attribution": ("qtimageformats/src/3rdparty/libtiff/qt_attribution.json"),
                "upstream_component": "libtiff 4.7.2",
                "upstream_condition": "Qt says it is used if system libtiff is not found.",
                "source_paths": ["LICENSES/libtiff.txt", "src/3rdparty/libtiff/COPYRIGHT"],
                "evidence_limit": (
                    "Source attribution only; the shipped binary's linkage is unverified."
                ),
            },
            {
                "plugin": "qwebp.dll",
                "source_archive": "qtimageformats-everywhere-src-6.12.0.tar.xz",
                "source_attribution": ("qtimageformats/src/3rdparty/libwebp/qt_attribution.json"),
                "upstream_component": "libwebp 1.6.0",
                "upstream_condition": "Qt says it is used if system libwebp is not found.",
                "source_paths": ["src/3rdparty/libwebp/COPYING"],
                "evidence_limit": (
                    "Source attribution only; the shipped binary's linkage is unverified."
                ),
            },
        ],
        "remaining_questions": [
            (
                "The PyPI Qt/PySide binary build provenance and exact linked third-party "
                "closure are not established by these source archives."
            ),
            (
                "The LGPL relinking and installation-information path still requires "
                "release acceptance."
            ),
            (
                "GPL-only components must be resolved against the exact shipped binaries "
                "before distribution approval."
            ),
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme = (
        "# Qt/PySide közleménycsomag\n\n"
        "Ez a mappa a hash-zárt Qt 6.12.0 és PySide 6.12.0 forrásarchívumokból "
        "kinyert licencszövegeket és upstream közleményeket tartalmazza. A "
        "`manifest.json` megadja minden fájl forrásarchívumát, belső útvonalát és "
        "SHA-256 hashét.\n\n"
        "A `qjpeg.dll`, `qtiff.dll` és `qwebp.dll` mellett megadott libjpeg-turbo, "
        "libtiff és libwebp közlemények forrásoldali jelöltek. A vendor binary "
        "buildlánc és a pontos linkelt komponensek nincsenek igazolva; ez a csomag "
        "nem licencmegfelelőségi jóváhagyás. A fennmaradó feltételek a manifestben "
        "és a RoboAssist #54 auditban szerepelnek.\n"
    )
    (output / "README.md").write_text(readme, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_bundle(args.source_dir, args.output)
    print(
        f"Qt license bundle staged: {len(manifest['files'])} source license/notice/attribution "
        "files "
        f"from {len(manifest['source_archives'])} hash-verified archives."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

