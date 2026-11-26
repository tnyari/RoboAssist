"""Explicit local WAV-to-events smoke; metadata only, no transcript/audio export."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from offline_stt.config import ConfigError, load_config
from offline_stt.pipeline import LocalEngineFactory, PipelineError, Session, WavSourceFactory


def main() -> int:
    parser = argparse.ArgumentParser(description="Helyi WAV → VAD → CPU INT8 session smoke")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--config", default="configs/default.toml")
    parser.add_argument("--catalog", default="models/manifest.json")
    parser.add_argument("--root", default="models/cache")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("--timeout must be 1..3600 seconds")
    session: Session | None = None
    counts = {"partial": 0, "final": 0}
    try:
        config = load_config(args.config)
        session = Session(
            config,
            WavSourceFactory(str(Path(args.wav).resolve()), frame_ms=config.audio.frame_ms),
            LocalEngineFactory(
                config, str(Path(args.catalog).resolve()), str(Path(args.root).resolve())
            ),
        )
        session.start()
        deadline = time.monotonic() + args.timeout
        while True:
            done = session.wait(0.05)
            for event in session.drain_events():
                counts[event.type] += 1
            if done:
                break
            if time.monotonic() >= deadline:
                session.stop()
                raise PipelineError("Replay smoke exceeded its requested timeout")
        if session.error:
            raise PipelineError(session.error)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "model": config.engine.model,
                    "events": counts,
                    "stats": asdict(session.stats),
                    "audio_saved": False,
                    "transcript_saved": False,
                    "scope": "local replay pipeline smoke; not speech accuracy or benchmark",
                },
                indent=2,
            )
        )
        return 0
    except (ConfigError, PipelineError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
