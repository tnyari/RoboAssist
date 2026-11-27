"""Stage NumPy without its private MSVC runtime copy for the Windows app.

The locked NumPy wheel uses delvewheel's hash-renamed MSVCP140 DLL in two
extension-module import tables. RoboAssist already installs the official
Microsoft VC Redistributable before launch, so this build-only overlay points
those imports at the standard system runtime name and omits NumPy's duplicate
copy from the packaged application. The locked wheel in site-packages is left
untouched.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import shutil
from pathlib import Path

import pefile


NUMPY_VERSION = "2.4.6"
PRIVATE_CRT = "msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll"
PRIVATE_CRT_SHA256 = "a4c2229bdc2a2a630acdc095b4d86008e5c3e3bc7773174354f3da4f5beb9cde"
PRIVATE_CRT_RECORD_HASH = "sha256=pMIim9wqKmMKzcCVtNhgCOXD47x3cxdDVPPaT1vrnN4"
SYSTEM_CRT = "msvcp140.dll"
EXPECTED_EXTENSIONS = {
    "numpy/_core/_multiarray_umath.cp311-win_amd64.pyd": (
        "sha256=T7TF1ipr12bupxY1Dq9TllgOM899wVnjBUiNG31y2tI",
        3_703_296,
    ),
    "numpy/fft/_pocketfft_umath.cp311-win_amd64.pyd": (
        "sha256=4i7lHJdh6MsuFT78Mh0Jy2VsVXNIjlUWf2nW4HDSJGY",
        276_480,
    ),
}
AMD64 = pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii")
    return "sha256=" + digest.rstrip("=")


def import_names(path: Path) -> list[bytes]:
    pe = pefile.PE(data=path.read_bytes(), fast_load=False)
    if pe.FILE_HEADER.Machine != AMD64:
        raise ValueError(f"Expected AMD64 NumPy extension: {path}")
    return [entry.dll.lower() for entry in pe.DIRECTORY_ENTRY_IMPORT]


def patch_import(path: Path) -> bytes:
    data = bytearray(path.read_bytes())
    pe = pefile.PE(data=bytes(data), fast_load=False)
    if pe.FILE_HEADER.Machine != AMD64:
        raise ValueError(f"Expected AMD64 NumPy extension: {path}")
    matches = [
        entry
        for entry in pe.DIRECTORY_ENTRY_IMPORT
        if entry.dll.lower() == PRIVATE_CRT.encode("ascii")
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one private MSVC import in {path}, found {len(matches)}")
    offset = pe.get_offset_from_rva(matches[0].struct.Name)
    old_name = PRIVATE_CRT.encode("ascii")
    new_name = SYSTEM_CRT.encode("ascii")
    if len(new_name) > len(old_name) or data[offset : offset + len(old_name) + 1] != old_name + b"\0":
        raise ValueError(f"Unexpected NumPy import string in {path}")
    data[offset : offset + len(new_name)] = new_name
    data[offset + len(new_name)] = 0
    return bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    site_packages = args.site_packages.resolve(strict=True)
    source_numpy = site_packages / "numpy"
    source_libs = site_packages / "numpy.libs"
    dist_info = site_packages / f"numpy-{NUMPY_VERSION}.dist-info"
    expected_output = (site_packages.parent.parent.parent / ".tools" / "numpy-system-msvc").resolve()
    output = args.output.resolve()
    if output != expected_output or output.parent != expected_output.parent:
        raise ValueError(f"Refusing unexpected staging path: {output}")
    if output.is_symlink():
        raise ValueError(f"Refusing to replace symlink staging path: {output}")
    if not all(path.is_dir() for path in (source_numpy, source_libs, dist_info)):
        raise FileNotFoundError("Expected NumPy 2.4.6 wheel directories are missing")

    metadata = (dist_info / "METADATA").read_text(encoding="utf-8")
    if f"Version: {NUMPY_VERSION}\n" not in metadata:
        raise ValueError("Installed NumPy version does not match the build pin")
    record_path = dist_info / "RECORD"
    with record_path.open("r", encoding="utf-8", newline="") as stream:
        source_rows = list(csv.reader(stream))
    source_record = {row[0]: row[1:] for row in source_rows if row}

    crt_path = source_libs / PRIVATE_CRT
    crt_data = crt_path.read_bytes()
    if sha256(crt_data) != PRIVATE_CRT_SHA256:
        raise ValueError("NumPy private MSVC DLL hash differs from the locked wheel")
    if source_record.get(f"numpy.libs/{PRIVATE_CRT}") != [PRIVATE_CRT_RECORD_HASH, str(len(crt_data))]:
        raise ValueError("NumPy RECORD does not match the pinned MSVC DLL")

    private_importers: set[str] = set()
    for pyd in source_numpy.rglob("*.pyd"):
        rel = pyd.relative_to(site_packages).as_posix()
        if PRIVATE_CRT.encode("ascii") in import_names(pyd):
            private_importers.add(rel)
    if private_importers != set(EXPECTED_EXTENSIONS):
        raise ValueError(f"Unexpected NumPy private MSVC importers: {sorted(private_importers)}")

    for rel, (expected_record_hash, expected_size) in EXPECTED_EXTENSIONS.items():
        payload = (site_packages / Path(rel)).read_bytes()
        record = source_record.get(rel)
        if record != [expected_record_hash, str(expected_size)]:
            raise ValueError(f"NumPy wheel RECORD pin mismatch: {rel}")
        if record_hash(payload) != expected_record_hash or len(payload) != expected_size:
            raise ValueError(f"NumPy extension differs from locked wheel: {rel}")

    if output.exists():
        if output.parent.resolve() != expected_output.parent:
            raise ValueError(f"Refusing to remove staging path outside .tools: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copytree(source_numpy, output / "numpy")
    shutil.copytree(
        source_libs,
        output / "numpy.libs",
        ignore=shutil.ignore_patterns(PRIVATE_CRT),
    )
    shutil.copytree(dist_info, output / dist_info.name)

    patched_rows = {row[0]: row for row in source_rows if row}
    for rel in EXPECTED_EXTENSIONS:
        staged_path = output / Path(rel)
        updated = patch_import(staged_path)
        staged_path.write_bytes(updated)
        if PRIVATE_CRT.encode("ascii") in import_names(staged_path):
            raise ValueError(f"Private MSVC import remains after patching: {rel}")
        if SYSTEM_CRT.encode("ascii") not in import_names(staged_path):
            raise ValueError(f"System MSVC import was not written: {rel}")
        patched_rows[rel] = [rel, record_hash(updated), str(len(updated))]
    patched_rows.pop(f"numpy.libs/{PRIVATE_CRT}", None)
    staged_record = output / dist_info.name / "RECORD"
    with staged_record.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(patched_rows.values())

    print(
        f"Staged NumPy {NUMPY_VERSION}: patched {len(EXPECTED_EXTENSIONS)} MSVC imports; "
        f"omitted {PRIVATE_CRT} ({PRIVATE_CRT_SHA256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

