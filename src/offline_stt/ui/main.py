"""Start the local-only Windows transcript window."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from offline_stt.config import ConfigError, load_config
from offline_stt.engines.models import ModelCatalog, ModelError
from offline_stt.ui.window import MainWindow


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[3]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RoboAssist helyi, offline feliratablak")
    parser.add_argument("--config", type=Path, help="Opcionális TOML konfiguráció")
    parser.add_argument("--catalog", type=Path, help="Helyi modellek manifestje")
    parser.add_argument("--model-root", type=Path, help="Helyi modellek könyvtára")
    return parser


def main() -> int:
    from multiprocessing import freeze_support

    freeze_support()
    args = _parser().parse_args()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    app = QApplication(sys.argv[:1])
    app.setOrganizationName("RoboAssist")
    app.setApplicationName("OfflineSTT")
    app.setApplicationDisplayName("RoboAssist · offline felirat")

    root = _resource_root()
    config_path = args.config or root / "configs" / "default.toml"
    catalog_path = args.catalog or root / "models" / "manifest.json"
    app_data = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    dev_model_root = root / "models" / "cache"
    model_root = args.model_root or (
        dev_model_root if dev_model_root.is_dir() else app_data / "models" / "cache"
    )
    try:
        config = load_config(config_path)
        catalog = ModelCatalog.read(catalog_path)
        installed = tuple(
            (spec.model_id.replace("-multilingual", "").capitalize(), spec.model_id)
            for spec in catalog.models
            if (model_root / spec.model_id / "install-receipt.json").is_file()
        )
    except (ConfigError, ModelError) as exc:
        QMessageBox.critical(None, "A RoboAssist nem indítható", str(exc))
        return 2

    window = MainWindow(config, catalog_path, model_root, installed)
    window.show()
    return app.exec()


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    raise SystemExit(main())
