"""Explicit local diagnostics. Reports counters only; never saves captured audio."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict

from offline_stt.audio import AudioSourceError, MicrophoneSource, input_devices


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboAssist helyi audioellenőrzés")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("devices", help="Bemeneti eszközlista; nincs hangrögzítés")
    mic = commands.add_parser("microphone", help="Explicit, csak memóriában futó mikrofonpróba")
    mic.add_argument("--device", type=int, required=True)
    mic.add_argument("--rate", type=int, choices=(44100, 48000), default=48000)
    mic.add_argument("--channels", type=int, choices=(1, 2), default=1)
    mic.add_argument("--seconds", type=float, default=3)
    mic.add_argument("--frame-ms", type=int, choices=(20, 30), default=20)
    args = parser.parse_args()
    source: MicrophoneSource | None = None
    try:
        if args.command == "devices":
            print(json.dumps([asdict(d) for d in input_devices()], ensure_ascii=True, indent=2))
            return 0
        if not math.isfinite(args.seconds) or not 0.1 <= args.seconds <= 30:
            parser.error("--seconds: 0.1..30 szükséges")
        source = MicrophoneSource(
            args.device, sample_rate=args.rate, channels=args.channels, frame_ms=args.frame_ms
        )
        print(
            "MIKROFONPRÓBA INDUL – csak memória, hangmentés és átirat nélkül.",
            file=sys.stderr,
            flush=True,
        )
        source.start()
        started = time.monotonic()
        target = math.ceil(args.seconds * 16000)
        expected = 0
        peak = 0.0
        energy = 0.0
        while expected < target:
            frame = source.read(timeout=0.1)
            if time.monotonic() - started > args.seconds + 5:
                raise AudioSourceError("A mikrofonpróba időkorlátja lejárt")
            if frame is None:
                continue
            if frame.start_sample != expected:
                raise AudioSourceError("Nem folytonos kimeneti mintaszám")
            expected = frame.end_sample
            peak = max(peak, float(abs(frame.samples).max()))
            energy += float((frame.samples.astype("float64") ** 2).sum())
        stats = asdict(source.stats)
        source.stop()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "device": args.device,
                    "rate": args.rate,
                    "channels": args.channels,
                    "frame_ms": args.frame_ms,
                    "stats": stats,
                    "peak": peak,
                    "rms": math.sqrt(energy / expected),
                    "audio_saved": False,
                    "scope": "capture, resampling, sample clock",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    except (AudioSourceError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    finally:
        if source is not None:
            try:
                source.close()
            except AudioSourceError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print("MIKROFONPRÓBA LEÁLLT – a forrás pufferei ürítve.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
