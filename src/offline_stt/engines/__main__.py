"""Local model verification, explicit installation and synthetic offline smoke."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from offline_stt.audio.types import AudioFrame
from offline_stt.engines import (
    EngineError,
    EngineOptions,
    FasterWhisperEngine,
    LocalModelStore,
    ModelError,
)


def main() -> int:
    resource_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    if getattr(sys, "_MEIPASS", None):
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        default_model_root = local_app_data / "RoboAssist" / "OfflineSTT" / "models" / "cache"
    else:
        default_model_root = resource_root / "models" / "cache"
    parser = argparse.ArgumentParser(description="RoboAssist helyi CPU INT8 modellek")
    parser.add_argument("--catalog", default=str(resource_root / "models" / "manifest.json"))
    parser.add_argument("--root", default=str(default_model_root))
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser(
        "verify", help="Helyi fájlok/hash-ek; nincs hálózat vagy modellbetöltés"
    )
    verify.add_argument("model")
    install = commands.add_parser("install", help="Külön explicit telepítés vagy offline import")
    install.add_argument("model")
    install.add_argument("--allow-network", action="store_true")
    install.add_argument("--from-directory")
    smoke = commands.add_parser(
        "smoke", help="Helyi modell, CPU INT8, szintetikus csend; nem benchmark"
    )
    smoke.add_argument("model")
    smoke.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    engine: FasterWhisperEngine | None = None
    try:
        store = LocalModelStore(args.catalog, args.root)
        if args.command == "install":
            from offline_stt.engines.install import install_model

            logging.basicConfig(level=logging.INFO, format="%(message)s")
            verified = install_model(
                store,
                args.model,
                allow_network=args.allow_network,
                source_directory=args.from_directory,
            )
            print(
                json.dumps(
                    {
                        "status": "verified",
                        "model": verified.spec.model_id,
                        "revision": verified.spec.revision,
                        "files": len(verified.spec.installed_files),
                    }
                )
            )
            return 0
        if args.command == "verify":
            verified = store.verify(args.model)
            print(
                json.dumps(
                    {
                        "status": "verified",
                        "model": verified.spec.model_id,
                        "revision": verified.spec.revision,
                        "network_used": False,
                    }
                )
            )
            return 0
        options = EngineOptions(cpu_threads=args.threads, max_new_tokens=16)
        engine = FasterWhisperEngine(store, args.model, options=options)
        engine.load()
        engine.load()  # Must not reload or warm up again.
        counts = []
        for _ in range(2):
            engine.reset()
            for start in range(0, 8000, 320):
                engine.push_audio(AudioFrame(np.zeros(320, dtype=np.float32), start, "wav"))
            result = engine.flush()
            assert result.start_sample == 0 and result.end_sample == 8000 and result.final
            assert engine.flush().segments == ()
            counts.append(len(result.segments))
        stats = asdict(engine.stats)
        if stats["model_loads"] != 1 or stats["warmup_calls"] != 1 or stats["decode_calls"] != 2:
            raise EngineError("Unexpected model/warm-up/decode lifecycle counts")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "model": args.model,
                    "revision": store.catalog.get(args.model).revision,
                    "device": "cpu",
                    "requested_compute_type": "int8",
                    "actual_compute_type": engine.compute_type,
                    "threads": args.threads,
                    "segment_counts": counts,
                    "stats": stats,
                    "audio_saved": False,
                    "transcript_saved": False,
                    "scope": "real model load/warm-up/reset/silence decode; not speech accuracy",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    except (ModelError, EngineError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            try:
                engine.close()
            except EngineError as exc:
                print(str(exc), file=sys.stderr)
                return 2


if __name__ == "__main__":
    raise SystemExit(main())
