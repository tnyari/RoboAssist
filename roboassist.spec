# -*- mode: python ; coding: utf-8 -*-

from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(SPECPATH).resolve()
sys.path.insert(0, str(ROOT / "src"))
from offline_stt.native_deps import configure_av_dll_search

configure_av_dll_search()

SITE_PACKAGES = Path(sys.prefix) / "Lib" / "site-packages"
AV_DLLS = SITE_PACKAGES / "av.libs"
AV_PACKAGE = SITE_PACKAGES / "av"
AV_LICENSES = ROOT / ".tools" / "av-vendor" / "av-runtime"
AV_SOURCE_ARCHIVES = ROOT / ".tools" / "av-vendor" / "upstream-sources"
PYTHON_LICENSES = ROOT / ".tools" / "python-license-bundle"
for required in (AV_DLLS, AV_PACKAGE, AV_LICENSES, AV_SOURCE_ARCHIVES, PYTHON_LICENSES):
    if not required.is_dir():
        raise SystemExit(f"Required staged build input is missing: {required}")

SOURCE_ARCHIVE_HASHES = {
    "av-17.1.0.tar.gz": "7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3",
    "ffmpeg-8.1.2.tar.gz": "32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22",
}
for filename, expected_hash in SOURCE_ARCHIVE_HASHES.items():
    source_archive = AV_SOURCE_ARCHIVES / filename
    if not source_archive.is_file():
        raise SystemExit(f"Required upstream source archive is missing: {source_archive}")
    actual_hash = sha256(source_archive.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(f"Upstream source hash mismatch for {source_archive}: {actual_hash}")


def tree_data(source: Path, destination: str) -> list[tuple[str, str]]:
    return [
        (str(path), str(Path(destination) / path.relative_to(source).parent))
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]


def package_modules(package: str, source: Path) -> list[str]:
    """Find importable Python/extension modules without importing native code."""
    modules = {package}
    for path in source.rglob("*"):
        if path.suffix == ".py":
            parts = list(path.relative_to(source).with_suffix("").parts)
        elif path.suffix == ".pyd":
            parts = [*path.parent.relative_to(source).parts, path.name.split(".", 1)[0]]
        else:
            continue
        if "__pycache__" in parts:
            continue
        if parts and parts[-1] == "__init__":
            parts.pop()
        modules.add(".".join((package, *parts)) if parts else package)
    return sorted(modules)

datas = [
    (str(ROOT / "configs" / "default.toml"), "configs"),
    (str(ROOT / "models" / "manifest.json"), "models"),
    (str(ROOT / "models" / "README.md"), "models"),
    (str(ROOT / "models" / "WHISPER_LICENSE.txt"), "models"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "LICENSE"), "licenses/RoboAssist"),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "docs" / "user-guide.md"), "docs"),
    (str(ROOT / "docs" / "benchmark-metrics.md"), "docs"),
]
datas += tree_data(AV_LICENSES, "licenses/av-runtime")
datas += tree_data(AV_SOURCE_ARCHIVES, "licenses/upstream-sources")
datas += [(str(ROOT / "docs" / "package" / "upstream-sources" / "README.md"), "licenses/upstream-sources")]
datas += tree_data(PYTHON_LICENSES, "licenses/python")
binaries = [(str(path), "av.libs") for path in sorted(AV_DLLS.glob("*.dll"))]
if not binaries:
    raise SystemExit("No staged PyAV/FFmpeg DLLs were found")

hiddenimports = [
    "faster_whisper",
    "ctranslate2",
    *package_modules("av", AV_PACKAGE),
]
common_analysis = {
    "pathex": [str(ROOT / "src")],
    "binaries": binaries,
    "datas": datas,
    "hiddenimports": hiddenimports,
    "hookspath": [],
    "hooksconfig": {},
    "runtime_hooks": [],
    "excludes": ["pytest", "ruff", "mypy"],
    "noarchive": False,
    "optimize": 0,
}

ui = Analysis(
    [str(ROOT / "src" / "offline_stt" / "ui" / "main.py")],
    **common_analysis,
)
manager = Analysis(
    [str(ROOT / "src" / "offline_stt" / "engines" / "__main__.py")],
    **common_analysis,
)
ui_pyz = PYZ(ui.pure)
manager_pyz = PYZ(manager.pure)
ui_exe = EXE(
    ui_pyz,
    ui.scripts,
    [],
    exclude_binaries=True,
    name="RoboAssist",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
manager_exe = EXE(
    manager_pyz,
    manager.scripts,
    [],
    exclude_binaries=True,
    name="RoboAssistModels",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    ui_exe,
    manager_exe,
    ui.binaries,
    manager.binaries,
    ui.datas,
    manager.datas,
    strip=False,
    upx=False,
    name="RoboAssist",
)
