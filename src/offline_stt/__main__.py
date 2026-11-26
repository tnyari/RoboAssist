"""Configuration validation CLI; does not start recording or load an engine."""

import argparse
import sys
from pathlib import Path

from offline_stt.config import ConfigError, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboAssist konfiguráció ellenőrzése")
    parser.add_argument("--config", required=True, type=Path, help="A TOML fájl elérési útja")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        f"Konfiguráció rendben: nyelv={config.application.language}, "
        f"engine={config.engine.backend}, {config.engine.device}/{config.engine.compute_type}, "
        f"offline={config.application.offline}, "
        f"save_audio={config.privacy.save_audio}, save_transcript={config.privacy.save_transcript}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
