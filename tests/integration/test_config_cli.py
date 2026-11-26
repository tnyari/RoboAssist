"""Validate installed entrypoints from a different working directory."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_installed_cli_from_another_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "offline_stt", "--config", str(ROOT / "configs/default.toml")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "cpu/int8" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_cli_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "offline_stt", "--config", str(tmp_path / "missing.toml")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "missing.toml" in result.stderr
    assert not result.stdout
