"""Stage the hash-locked conda-forge PyAV build and its exact DLL closure."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AV = ("17.1.0", "py311h06a8702_0")
EXPECTED_FFMPEG = ("8.1.2", "lgpl_haba0ffa_812")
WINDOWS_DLLS = {
    "advapi32.dll",
    "bcrypt.dll",
    "bcryptprimitives.dll",
    "cfgmgr32.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "cryptbase.dll",
    "d3d11.dll",
    "d3d12.dll",
    "d3dcompiler_47.dll",
    "dbghelp.dll",
    "dnsapi.dll",
    "dwmapi.dll",
    "gdi32.dll",
    "gdi32full.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "kernelbase.dll",
    "mf.dll",
    "mfplat.dll",
    "mfreadwrite.dll",
    "mpr.dll",
    "msvcrt.dll",
    "mswsock.dll",
    "netapi32.dll",
    "ncrypt.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleacc.dll",
    "oleaut32.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "secur32.dll",
    "setupapi.dll",
    "shcore.dll",
    "shell32.dll",
    "shlwapi.dll",
    "user32.dll",
    "userenv.dll",
    "uxtheme.dll",
    "version.dll",
    "win32u.dll",
    "wininet.dll",
    "winmm.dll",
    "winspool.drv",
    "ws2_32.dll",
    "wtsapi32.dll",
    "wldap32.dll",
    "windowscodecs.dll",
    "python3.dll",
    "python311.dll",
}


def _inside_root(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise SystemExit(f"{label} must be inside the repository: {resolved}")
    return resolved


def _pe_imports(path: Path) -> list[str]:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise RuntimeError(f"Not a PE binary: {path}")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError(f"Invalid PE header: {path}")
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    if machine != 0x8664:
        raise RuntimeError(f"Expected Windows x64 binary, got machine 0x{machine:04x}: {path}")
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic != 0x20B:
        raise RuntimeError(f"Expected PE32+ binary: {path}")
    directory = optional + 112
    import_rva, _ = struct.unpack_from("<II", data, directory + 8)
    section_table = optional + optional_size
    sections: list[tuple[int, int, int]] = []
    for index in range(section_count):
        offset = section_table + 40 * index
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        sections.append((virtual_address, max(virtual_size, raw_size), raw_offset))

    def file_offset(rva: int) -> int | None:
        for address, size, offset in sections:
            if address <= rva < address + size:
                return offset + rva - address
        return None

    cursor = file_offset(import_rva)
    if cursor is None:
        if import_rva == 0:
            return []
        raise RuntimeError(f"Import table is outside PE sections: {path}")
    imports: list[str] = []
    while cursor + 20 <= len(data):
        original, _, _, name_rva, thunk = struct.unpack_from("<IIIII", data, cursor)
        if not (original or name_rva or thunk):
            break
        name_offset = file_offset(name_rva)
        if name_offset is None:
            raise RuntimeError(f"Invalid DLL import in {path}")
        end = data.find(b"\0", name_offset)
        if end < 0:
            raise RuntimeError(f"Unterminated DLL import in {path}")
        imports.append(data[name_offset:end].decode("ascii", "strict").lower())
        cursor += 20
    return imports


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_remove(path: Path, parent: Path) -> None:
    resolved_parent = parent.resolve()
    resolved = path.resolve()
    if resolved.parent != resolved_parent or resolved.name in {"", ".", ".."}:
        raise SystemExit(f"Refusing to remove an unexpected path: {resolved}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def _package_rows(prefix: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for path in (prefix / "conda-meta").glob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        rows[str(row["name"]).lower()] = row
    return rows


def _verify_ffmpeg_configuration(configuration: str) -> dict[str, bool]:
    """Require the staged FFmpeg build's LGPLv3 configuration and reject GPL/nonfree flags."""
    tokens = set(configuration.split())
    flags = {
        "disable_gpl": "--disable-gpl" in tokens,
        "enable_version3": "--enable-version3" in tokens,
        "enable_gpl": "--enable-gpl" in tokens,
        "enable_nonfree": "--enable-nonfree" in tokens,
        "enable_libx264": "--enable-libx264" in tokens,
        "enable_libx265": "--enable-libx265" in tokens,
    }
    if not flags["disable_gpl"] or not flags["enable_version3"]:
        raise RuntimeError("The staged FFmpeg DLL must report --disable-gpl and --enable-version3.")
    forbidden = [
        name
        for name in ("enable_gpl", "enable_nonfree", "enable_libx264", "enable_libx265")
        if flags[name]
    ]
    if forbidden:
        raise RuntimeError(f"The staged FFmpeg DLL enables forbidden build flags: {forbidden}")
    return flags


def _ffmpeg_configuration_from_dll(avcodec_path: Path) -> str:
    if not avcodec_path.is_file():
        raise RuntimeError(f"The staged FFmpeg codec DLL is missing: {avcodec_path}")
    try:
        with os.add_dll_directory(str(avcodec_path.parent)):
            library = ctypes.WinDLL(str(avcodec_path))
            query = library.avcodec_configuration
            query.restype = ctypes.c_char_p
            result = query()
    except (AttributeError, OSError) as exc:
        raise RuntimeError(f"Could not read FFmpeg configuration from {avcodec_path}") from exc
    if not result:
        raise RuntimeError(f"FFmpeg returned an empty build configuration: {avcodec_path}")
    return result.decode("utf-8")


def _runtime_dlls(prefix: Path, av_dir: Path) -> list[Path]:
    dll_root = prefix / "Library" / "bin"
    available: dict[str, Path] = {}
    for path in dll_root.glob("*.dll"):
        key = path.name.lower()
        previous = available.get(key)
        if previous and _sha256(previous) != _sha256(path):
            raise RuntimeError(f"Two different conda DLLs have the same name: {previous}, {path}")
        available[key] = path

    queue = list(av_dir.rglob("*.pyd"))
    visited: set[Path] = set()
    required: dict[str, Path] = {}
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32"
    unresolved: set[str] = set()
    while queue:
        binary = queue.pop()
        binary_key = binary.resolve()
        if binary_key in visited:
            continue
        visited.add(binary_key)
        for imported in _pe_imports(binary):
            if imported.startswith(("api-ms-win-", "ext-ms-win-")):
                continue
            dll = available.get(imported)
            if dll:
                required[imported] = dll
                queue.append(dll)
            elif imported in WINDOWS_DLLS or (windows_dir / imported).is_file():
                continue
            else:
                unresolved.add(imported)
    if unresolved:
        raise RuntimeError("Unresolved non-Windows DLL imports: " + ", ".join(sorted(unresolved)))
    if not required:
        raise RuntimeError("No conda-forge PyAV runtime DLLs were found")
    if any(re.match(r"^(lib)?x26[05].*\.dll$", name) for name in required):
        raise RuntimeError("The selected LGPL FFmpeg DLL closure unexpectedly contains x264/x265")
    return sorted(required.values(), key=lambda item: item.name.casefold())


def _copy_package_metadata(
    row: dict[str, object], output: Path, *, fallback_licenses: Path | None = None
) -> dict[str, object]:
    name = str(row["name"])
    version = str(row["version"])
    build = str(row["build"])
    artifact_dir = Path(str(row.get("extracted_package_dir") or ""))
    if not artifact_dir.is_dir():
        raise RuntimeError(f"Conda package cache is missing for {name}: {artifact_dir}")
    info = artifact_dir / "info"
    license_source = info / "licenses"
    if not any(path.is_file() for path in license_source.rglob("*")):
        about_path = info / "about.json"
        about = json.loads(about_path.read_text(encoding="utf-8")) if about_path.is_file() else {}
        source_identity = (
            about.get("extra", {}).get("remote_url"),
            about.get("extra", {}).get("sha"),
        )
        if all(source_identity):
            for sibling in artifact_dir.parent.iterdir():
                candidate_about = sibling / "info" / "about.json"
                candidate_licenses = sibling / "info" / "licenses"
                if not candidate_about.is_file() or not candidate_licenses.is_dir():
                    continue
                candidate = json.loads(candidate_about.read_text(encoding="utf-8"))
                candidate_identity = (
                    candidate.get("extra", {}).get("remote_url"),
                    candidate.get("extra", {}).get("sha"),
                )
                if candidate_identity == source_identity and any(
                    item.is_file() for item in candidate_licenses.rglob("*")
                ):
                    license_source = candidate_licenses
                    break
    if not any(path.is_file() for path in license_source.rglob("*")):
        if fallback_licenses is None or not fallback_licenses.is_dir():
            raise RuntimeError(f"No license text found for conda package {name} {version}")
        license_source = fallback_licenses

    slug = re.sub(r"[^A-Za-z0-9_.+-]", "_", f"{name}-{version}-{build}")
    package_dir = output / "packages" / slug
    license_dir = package_dir / "licenses"
    source_dir = package_dir / "source-build-info"
    _safe_remove(package_dir, output / "packages")
    license_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)
    for source in license_source.rglob("*"):
        if source.is_file():
            target = license_dir / source.relative_to(license_source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for filename in ("about.json", "index.json", "repodata_record.json"):
        source = info / filename
        if source.is_file():
            shutil.copy2(source, source_dir / filename)
    recipe = info / "recipe"
    if recipe.is_dir():
        shutil.copytree(recipe, source_dir / "recipe", dirs_exist_ok=True)
    return {
        "name": name,
        "version": version,
        "build": build,
        "license": row.get("license", "unknown"),
        "artifact_url": row.get("url"),
        "artifact_sha256": row.get("sha256"),
        "license_files": sorted(
            str(item.relative_to(package_dir)).replace("\\", "/")
            for item in license_dir.rglob("*")
            if item.is_file()
        ),
        "source_build_metadata": str((source_dir / "recipe").relative_to(output)).replace(
            "\\", "/"
        ),
    }


def stage(prefix: Path, site_packages: Path, distribution_root: Path) -> dict[str, object]:
    prefix = _inside_root(prefix, "Conda prefix")
    site_packages = _inside_root(site_packages, "Python site-packages")
    distribution_root = _inside_root(distribution_root, "Distribution staging directory")
    conda_sites = prefix / "Lib" / "site-packages"
    av_source = conda_sites / "av"
    dist_infos = sorted(conda_sites.glob("av-*.dist-info"))
    if not av_source.is_dir() or len(dist_infos) != 1:
        raise RuntimeError("The locked conda-forge PyAV package is missing or ambiguous")
    av_info = json.loads(
        (prefix / "conda-meta" / "av-17.1.0-py311h06a8702_0.json").read_text(encoding="utf-8")
    )
    ffmpeg_info = json.loads(
        (prefix / "conda-meta" / "ffmpeg-8.1.2-lgpl_haba0ffa_812.json").read_text(encoding="utf-8")
    )
    if (av_info["version"], av_info["build"]) != EXPECTED_AV:
        raise RuntimeError(f"Unexpected PyAV artifact: {av_info['version']} {av_info['build']}")
    if (ffmpeg_info["version"], ffmpeg_info["build"]) != EXPECTED_FFMPEG:
        raise RuntimeError(
            f"Unexpected FFmpeg artifact: {ffmpeg_info['version']} {ffmpeg_info['build']}"
        )
    if ffmpeg_info.get("license") != "LGPL-2.1-or-later":
        raise RuntimeError(f"Unexpected FFmpeg license metadata: {ffmpeg_info.get('license')}")

    ffmpeg_flags = _verify_ffmpeg_configuration(
        _ffmpeg_configuration_from_dll(prefix / "Library" / "bin" / "avcodec-62.dll")
    )
    dlls = _runtime_dlls(prefix, av_source)
    rows = _package_rows(prefix)
    owners: dict[str, set[str]] = {}
    for name, row in rows.items():
        for filename in row.get("files", []):
            normalized = str(filename).replace("\\", "/").lower()
            if normalized.startswith("library/bin/") and normalized.endswith(".dll"):
                owners.setdefault(normalized.rsplit("/", 1)[-1], set()).add(name)

    package_names = {"av"}
    dll_records: list[dict[str, str | int]] = []
    for source in dlls:
        owner_names = owners.get(source.name.lower(), set())
        if not owner_names:
            raise RuntimeError(f"No conda package owner recorded for {source.name}")
        package_names.update(owner_names)
        dll_records.append(
            {"name": source.name, "size": source.stat().st_size, "sha256": _sha256(source)}
        )

    site_packages.mkdir(parents=True, exist_ok=True)
    for old in [
        site_packages / "av",
        site_packages / "av.libs",
        *site_packages.glob("av-*.dist-info"),
    ]:
        _safe_remove(old, site_packages)
    shutil.copytree(
        av_source, site_packages / "av", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copytree(
        dist_infos[0],
        site_packages / dist_infos[0].name,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    staged_dll_dir = site_packages / "av.libs"
    staged_dll_dir.mkdir()
    for source in dlls:
        shutil.copy2(source, staged_dll_dir / source.name)

    _safe_remove(distribution_root / "av-runtime", distribution_root)
    output = distribution_root / "av-runtime"
    output.mkdir(parents=True)
    package_records = []
    for name in sorted(package_names):
        row = rows.get(name)
        if row is None:
            raise RuntimeError(f"Conda package metadata is missing for {name}")
        fallback = None
        if name == "av":
            fallback = dist_infos[0] / "licenses"
        package_records.append(_copy_package_metadata(row, output, fallback_licenses=fallback))

    manifest = {
        "platform": "win-64",
        "python_abi": "cp311",
        "pyav": {"version": EXPECTED_AV[0], "build": EXPECTED_AV[1]},
        "ffmpeg": {
            "version": EXPECTED_FFMPEG[0],
            "build": EXPECTED_FFMPEG[1],
            "license": "LGPL-2.1-or-later",
            "configured_license_version": "LGPLv3",
        },
        "runtime_dll_count": len(dll_records),
        "runtime_dll_size_bytes": sum(int(item["size"]) for item in dll_records),
        "runtime_dlls": dll_records,
        "conda_packages": package_records,
        "verification": {
            "gpl_codecs_excluded_by_build_variant": True,
            "gpl_only_x264_x265_dlls_in_runtime_closure": False,
            "ffmpeg_configuration_source": "avcodec_configuration() from avcodec-62.dll",
            "ffmpeg_configuration_flags": ffmpeg_flags,
            "basis": (
                "Exact conda-forge package build string, avcodec-62.dll configuration "
                "(--disable-gpl and --enable-version3), and PE import closure. "
                "The package metadata declares LGPL-2.1-or-later; the selected build "
                "configuration uses LGPLv3."
            ),
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# PyAV / FFmpeg runtime notice bundle",
        "",
        "This folder accompanies the dynamically linked PyAV runtime. License texts, exact conda",
        "artifacts, source hashes and the conda-forge build recipes are preserved per package.",
        "The packaged FFmpeg DLL configuration verifies LGPLv3; GPL and nonfree configure flags "
        "are disabled. The staged PE dependency closure contains no x264/x265 DLLs. This manifest "
        "is build evidence, not a legal opinion.",
        "",
        "| Package | Version / build | Declared license | Artifact SHA-256 |",
        "|---|---|---|---|",
    ]
    for item in package_records:
        lines.append(
            f"| {item['name']} | {item['version']} / `{item['build']}` | "
            f"{item['license']} | `{item['artifact_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "Each package folder contains the artifact license texts and, when supplied with the",
            "artifact, the exact `info/recipe`, `info/about.json`, `info/index.json`, and",
            "`info/repodata_record.json`. The FFmpeg recipe records its source archive URL and",
            "SHA-256 as well as the LGPL build configuration. See `manifest.json` for the full",
            "DLL closure and artifact URLs.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conda-prefix", type=Path, required=True)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--distribution-root", type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.conda_prefix, args.site_packages, args.distribution_root)
    print(
        f"Staged PyAV {result['pyav']['version']} + FFmpeg {result['ffmpeg']['version']} "
        f"({result['ffmpeg']['configured_license_version']} verified): "
        f"{result['runtime_dll_count']} DLLs, {result['runtime_dll_size_bytes']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
