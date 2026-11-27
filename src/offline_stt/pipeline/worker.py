"""Spawn child: source reader, VAD scheduler and one serialized STT worker."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Event as ProcessEvent
from threading import Event, Lock, Thread

from offline_stt.audio.types import AudioSource, SourceState
from offline_stt.config import Config
from offline_stt.engines.types import SpeechEngine
from offline_stt.pipeline.events import Stabilizer
from offline_stt.pipeline.scheduling import Counters, FrameQueue, JobQueue
from offline_stt.pipeline.types import PipelineError
from offline_stt.pipeline.vad import Segmenter

SourceFactory = Callable[[], AudioSource]
EngineFactory = Callable[[], SpeechEngine]


def run_session(
    session_id: str,
    config: Config,
    source_factory: SourceFactory,
    engine_factory: EngineFactory,
    stop: ProcessEvent,
    output: Connection,
) -> None:
    """All audio/engine resources stay inside this killable process."""
    counters = Counters()
    frames = FrameQueue(config.pipeline.frame_queue_capacity, counters)
    jobs = JobQueue(config.pipeline.final_queue_capacity, counters)
    quit_reader, reader_done, engine_ready, source_ready = Event(), Event(), Event(), Event()
    failures: list[str] = []  # At most first failure; guarded across the three threads.
    failure_lock, output_lock = Lock(), Lock()

    def send(kind: str, value: object = None) -> None:
        with output_lock:
            output.send((kind, value))

    def fail(message: str) -> None:
        with failure_lock:
            if not failures:
                failures.append(message[:2048])
        quit_reader.set()
        jobs.finish(abort=True)
        engine_ready.set()
        source_ready.set()

    def reader() -> None:
        source: AudioSource | None = None
        try:
            source = source_factory()
            source.start()
            source_start = source.stats.started_monotonic
            counters.set(
                "source_started_monotonic_ns",
                time.monotonic_ns()
                if source_start is None
                else round(source_start * 1_000_000_000),
            )
            source_ready.set()
            while not quit_reader.is_set() and not stop.is_set():
                frame = source.read(timeout=0.05)
                if frame is not None:
                    mean_square = math.fsum(float(sample) ** 2 for sample in frame.samples) / len(
                        frame.samples
                    )
                    rms = math.sqrt(mean_square)
                    level = 20 * math.log10(max(rms, 1e-6))
                    counters.set("input_level_dbfs", max(-120.0, min(0.0, level)))
                    frames.put(frame)
                elif source.state == SourceState.ENDED:
                    break
                elif source.state != SourceState.RUNNING:
                    raise PipelineError(source.error or "Audio source stopped unexpectedly")
        except Exception as exc:
            fail(f"Source/queue failure: {exc}")
        finally:
            if source is not None:
                try:
                    stats = source.stats
                    counters.add("dropped_frames", stats.dropped_blocks)
                    counters.add("dropped_samples", stats.dropped_samples)
                    source.close()
                except Exception as exc:
                    fail(f"Source cleanup failure: {exc}")
            reader_done.set()
            source_ready.set()

    def decoder() -> None:
        engine: SpeechEngine | None = None
        stabilizer = Stabilizer(session_id)
        segment = previous_start = previous_end = 0
        try:
            engine = engine_factory()
            engine.load()
            counters.add("engine_model_loads", engine.stats.model_loads)
            counters.add("engine_warmup_calls", engine.stats.warmup_calls)
            engine_ready.set()
            while (job := jobs.get()) is not None:
                counters.set("decoder_busy", True)
                try:
                    engine.reset(start_sample=job.frame.start_sample)
                    engine.push_audio(job.frame)
                    result = engine.flush() if job.final else engine.preview()
                    kind = "final" if job.final else "partial"
                    counters.add(kind + "_decodes")
                    counters.add(kind + "_decode_seconds", result.decode_seconds)
                    counters.add("decoded_audio_samples", len(job.frame.samples))
                    if segment == job.segment:
                        overlap = max(
                            0,
                            min(previous_end, job.frame.end_sample)
                            - max(previous_start, job.frame.start_sample),
                        )
                        counters.add("repeated_decode_samples", overlap)
                    else:
                        segment = job.segment
                        previous_start = job.frame.start_sample
                    previous_end = max(
                        previous_end if segment == job.segment else 0, job.frame.end_sample
                    )
                    if jobs.stale(job):
                        if not job.final:
                            counters.add("partial_jobs_dropped")
                        continue
                    event = stabilizer.accept(job, result)
                    if event is not None:
                        send("event", event)
                finally:
                    counters.set("decoder_busy", False)
        except Exception as exc:
            fail(f"Engine failure: {exc}")
        finally:
            if engine is not None:
                try:
                    engine.close()
                except Exception as exc:
                    fail(f"Engine cleanup failure: {exc}")
            engine_ready.set()

    decode_thread = Thread(target=decoder, name="STT decoder", daemon=True)
    read_thread = Thread(target=reader, name="Audio reader", daemon=True)
    try:
        decode_thread.start()
        while not engine_ready.wait(0.02):
            # Parent Stop deadline can terminate a blocked load/warm-up.
            pass
        if failures:
            raise PipelineError(failures[0])
        read_thread.start()
        source_ready.wait()
        if failures:
            raise PipelineError(failures[0])
        send("ready")
        segmenter = Segmenter(config, jobs.put)
        next_stats = 0.0
        while True:
            if failures:
                raise PipelineError(failures[0])
            frame, drained = frames.next(reader_done)
            if frame is not None:
                segmenter.push(frame)
            elif drained:
                break
            if time.monotonic() >= next_stats:
                send("stats", counters.snapshot())
                next_stats = time.monotonic() + 0.1
        segmenter.flush()
        jobs.finish()
        decode_thread.join()  # Parent owns the bounded Stop/terminate deadline.
        if failures:
            raise PipelineError(failures[0])
    except Exception as exc:
        fail(str(exc))
        send("error", failures[0])
    finally:
        quit_reader.set()
        jobs.finish(abort=bool(failures))
        if read_thread.ident is not None:
            read_thread.join()
        if decode_thread.ident is not None:
            decode_thread.join()
        send("stats", counters.snapshot())
        send("done")
        output.close()
