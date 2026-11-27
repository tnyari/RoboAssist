# -*- mode: python ; coding: utf-8 -*-

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(SPECPATH).resolve()
sys.path.insert(0, str(ROOT / "src"))
from offline_stt.native_deps import configure_av_dll_search

configure_av_dll_search()

SITE_PACKAGES = Path(sys.prefix) / "Lib" / "site-packages"
NUMPY_STAGE = ROOT / ".tools" / "numpy-system-msvc"
AV_DLLS = SITE_PACKAGES / "av.libs"
AV_PACKAGE = SITE_PACKAGES / "av"
AV_LICENSES = ROOT / ".tools" / "av-vendor" / "av-runtime"
UPSTREAM_SOURCE_ARCHIVES = ROOT / ".tools" / "av-vendor" / "upstream-sources"
PYTHON_LICENSES = ROOT / ".tools" / "python-license-bundle"
QT_LICENSES = ROOT / ".tools" / "qt-license-bundle"
VC_RUNTIME_MANIFEST = ROOT / "docs" / "package" / "vc-runtime.json"
with VC_RUNTIME_MANIFEST.open("r", encoding="utf-8") as stream:
    vc_runtime = json.load(stream)
VC_RUNTIME_INSTALLER = ROOT / ".tools" / vc_runtime["filename"]
for required in (
    NUMPY_STAGE,
    AV_DLLS,
    AV_PACKAGE,
    AV_LICENSES,
    UPSTREAM_SOURCE_ARCHIVES,
    PYTHON_LICENSES,
    QT_LICENSES,
    VC_RUNTIME_INSTALLER.parent,
):
    if not required.is_dir():
        raise SystemExit(f"Required staged build input is missing: {required}")
sys.path.insert(0, str(NUMPY_STAGE))

SOURCE_ARCHIVE_HASHES = {
    "av-17.1.0.tar.gz": "7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3",
    "ffmpeg-8.1.2.tar.gz": "32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22",
    "qtbase-everywhere-src-6.12.0.tar.xz": "a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307",
    "qtsvg-everywhere-src-6.12.0.tar.xz": "e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331",
    "qtimageformats-everywhere-src-6.12.0.tar.xz": "0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762",
    "pyside-setup-v6.12.0.tar.gz": "dce2a944b34320e51a0ec8100cb983956399b97dec386f0fbe39e1b52571a336",
    "openssl-3.5.9.tar.gz": "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a",
    "cpython-3.11.18+20261124-x86_64-pc-windows-msvc-install_only.tar.gz": "3e4a35e3c238e5090d36bf95c041d9052bc82d6e298cb912ba7f70f6c66cf81a",
    "Python-3.11.18.tgz": "5f62711b12470fd435f83f1451c1b1ef4a179aebc715c716874b0967567d814e",
    "python-build-standalone-48d61fcd7d85d7013b95576f62f779008c316a63.tar.gz": "ca344c08ea7717d1b81fc915f4545098e0c60483137dbc47ce3c3588389e53dc",
}
for filename, expected_hash in SOURCE_ARCHIVE_HASHES.items():
    source_archive = UPSTREAM_SOURCE_ARCHIVES / filename
    if not source_archive.is_file():
        raise SystemExit(f"Required upstream source archive is missing: {source_archive}")
    actual_hash = sha256(source_archive.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(f"Upstream source hash mismatch for {source_archive}: {actual_hash}")

actual_vc_runtime_hash = sha256(VC_RUNTIME_INSTALLER.read_bytes()).hexdigest()
if actual_vc_runtime_hash != vc_runtime["sha256"]:
    raise SystemExit(f"VC Redistributable hash mismatch: {actual_vc_runtime_hash}")


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
datas += tree_data(UPSTREAM_SOURCE_ARCHIVES, "licenses/upstream-sources")
datas += [(str(ROOT / "docs" / "package" / "upstream-sources" / "README.md"), "licenses/upstream-sources")]
datas += tree_data(PYTHON_LICENSES, "licenses/python")
datas += tree_data(QT_LICENSES, "licenses/qt")
datas += [
    (str(VC_RUNTIME_INSTALLER), "runtime"),
    (str(VC_RUNTIME_MANIFEST), "runtime"),
]
binaries = [(str(path), "av.libs") for path in sorted(AV_DLLS.glob("*.dll"))]
if not binaries:
    raise SystemExit("No staged PyAV/FFmpeg DLLs were found")

hiddenimports = [
    "faster_whisper",
    "ctranslate2",
    *package_modules("av", AV_PACKAGE),
]
common_analysis = {
    "pathex": [str(NUMPY_STAGE), str(ROOT / "src")],
    "binaries": binaries,
    "datas": datas,
    "hiddenimports": hiddenimports,
    "hookspath": [str(ROOT / "hooks")],
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

# The official, hash-locked VC Redistributable is installed once through the
# package launcher. Do not ship duplicate app-local MSVC/UCRT runtime DLLs.
SYSTEM_RUNTIME_DLLS = {
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "ucrtbase.dll",
    "vccorlib140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
}
NUMPY_PRIVATE_CRT_DLL = "msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll"


def without_system_runtime_dlls(entries: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    filtered = []
    for entry in entries:
        filename = Path(entry[0]).name.casefold()
        # Windows 10/11 resolves these API-set contract names through the OS
        # schema; they are not app-local DLL dependencies.
        is_api_set_contract = filename.startswith(("api-ms-win-", "ext-ms-win-"))
        if (
            filename not in SYSTEM_RUNTIME_DLLS
            and filename != NUMPY_PRIVATE_CRT_DLL
            and not is_api_set_contract
        ):
            filtered.append(entry)
    return filtered


ui_binaries = without_system_runtime_dlls(ui.binaries)
manager_binaries = without_system_runtime_dlls(manager.binaries)
remaining_runtime_dlls = {
    Path(entry[0]).name.casefold() for entry in (*ui_binaries, *manager_binaries)
} & SYSTEM_RUNTIME_DLLS
if remaining_runtime_dlls:
    raise SystemExit(f"App-local system runtime DLLs remain: {sorted(remaining_runtime_dlls)}")

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
    ui_binaries,
    manager_binaries,
    ui.datas,
    manager.datas,
    strip=False,
    upx=False,
    name="RoboAssist",
)
