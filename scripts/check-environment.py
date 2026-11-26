"""Offline dependency/DLL smoke test. No model, microphone or audio files needed."""

import importlib.metadata
import json
import os
import platform
import socket
import struct
import sys
from pathlib import Path
from unittest.mock import patch


def deny_network(*args: object, **kwargs: object) -> None:
    raise RuntimeError("Unexpected network access during environment smoke test")


def main() -> None:
    assert sys.version_info[:2] == (3, 11), sys.version
    assert struct.calcsize("P") == 8
    assert sys.platform == "win32"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    with (
        patch.object(socket, "getaddrinfo", deny_network),
        patch.object(socket.socket, "connect", deny_network),
        patch.object(socket.socket, "connect_ex", deny_network),
    ):
        import av
        import ctranslate2
        import faster_whisper
        import numpy as np
        import onnxruntime
        import sounddevice
        import tokenizers
        from PySide6.QtCore import qVersion
        from PySide6.QtWidgets import QApplication, QLabel

        from offline_stt.config import load_config

        config = load_config(Path(__file__).resolve().parents[1] / "configs/default.toml")
        assert config.application.offline
        compute_types = ctranslate2.get_supported_compute_types("cpu")
        assert "int8" in compute_types, compute_types
        assert "CPUExecutionProvider" in onnxruntime.get_available_providers()
        assert callable(faster_whisper.WhisperModel)
        assert tokenizers.Tokenizer is not None
        assert av.AudioFrame(format="s16", layout="mono", samples=320).samples == 320
        assert np.zeros(320, dtype=np.float32).shape == (320,)
        portaudio_version = sounddevice.get_portaudio_version()[1]
        app = QApplication([])
        label = QLabel("RoboAssist – magyar felirat")
        label.resize(320, 80)
        assert not label.grab().isNull()
        label.close()
        app.processEvents()
        app.quit()

    packages = [
        "roboassist-offline-stt",
        "faster-whisper",
        "ctranslate2",
        "numpy",
        "PySide6-Essentials",
        "shiboken6",
        "sounddevice",
        "onnxruntime",
        "av",
    ]
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "bits": 64,
                "packages": {name: importlib.metadata.version(name) for name in packages},
                "qt": qVersion(),
                "portaudio": portaudio_version,
                "cpu_compute_types": sorted(compute_types),
                "status": "passed",
                "scope": (
                    "imports, DLLs, CPU INT8 availability, offscreen Qt, config; no model inference"
                ),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
