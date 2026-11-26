"""Sample-clock VAD, priority/backpressure and immutable event regressions."""

from dataclasses import FrozenInstanceError, replace
from threading import Event

import numpy as np
import pytest

from offline_stt.audio import AudioFrame
from offline_stt.config import Config, ConfigError, PipelineConfig, VadConfig
from offline_stt.engines.types import DecodedSegment, DecodeResult
from offline_stt.pipeline.events import Stabilizer
from offline_stt.pipeline.scheduling import Counters, DecodeJob, FrameQueue, JobQueue
from offline_stt.pipeline.types import PipelineError
from offline_stt.pipeline.vad import EnergyVad, Segmenter


def frame(start=0, value=0.2, count=320):
    return AudioFrame(np.full(count, value, dtype="float32"), start, "wav")


def job(number=1, start=0, end=16000, final=False):
    return DecodeJob(number, 0, frame(start, count=end - start), final)


def result(work, *parts):
    segments = tuple(DecodedSegment(a, b, text) for a, b, text in parts)
    return DecodeResult(
        work.frame.start_sample, work.frame.end_sample, "hu", segments, work.final, 0.1
    )


def test_energy_threshold_release_hysteresis_and_silence():
    vad = EnergyVad(-40, 6)
    assert not vad.speech(frame(value=0), False)
    assert vad.speech(frame(value=0.02), False)
    assert not vad.speech(frame(value=0.007), False)
    assert vad.speech(frame(value=0.007), True)


def test_silence_has_no_jobs_and_preroll_has_exact_sample_bound():
    jobs = []
    segmenter = Segmenter(Config(), jobs.append)
    for start in range(0, 16000, 320):
        segmenter.push(frame(start, 0))
    assert not jobs
    segmenter.push(frame(16000))
    for start in range(16320, 24320, 320):
        segmenter.push(frame(start, 0))
    finals = [j for j in jobs if j.final]
    assert len(finals) == 1
    assert finals[0].frame.start_sample == 12000  # 250 ms, independent of frame rounding
    assert finals[0].frame.end_sample == 24320
    assert len(finals[0].frame.samples) == 12320
    segmenter.flush()
    segmenter.flush()
    assert len([j for j in jobs if j.final]) == 1


def test_long_speech_splits_without_gaps_or_overlapping_finals_and_rolls_partials():
    jobs = []
    segmenter = Segmenter(Config(), jobs.append)
    for start in range(0, 16 * 16000, 320):
        segmenter.push(frame(start))
    segmenter.flush()
    finals = [j for j in jobs if j.final]
    assert [(j.frame.start_sample, j.frame.end_sample) for j in finals] == [
        (0, 192000),
        (192000, 256000),
    ]
    partials = [j for j in jobs if not j.final]
    assert partials[0].frame.end_sample == 12160  # frame-end rounding of 750 ms
    assert max(len(j.frame.samples) for j in partials) == 80000
    assert any(j.frame.start_sample > 0 for j in partials if j.segment == 1)
    assert all(len(j.frame.samples) <= 80000 for j in partials)


def test_quick_alternation_short_segment_stop_and_discontinuity():
    jobs = []
    segmenter = Segmenter(Config(), jobs.append)
    for index in range(20):
        segmenter.push(frame(index * 320, 0.2 if index % 2 else 0))
    segmenter.flush()
    assert len([j for j in jobs if j.final]) == 1
    with pytest.raises(PipelineError, match="Discontinuous"):
        segmenter.push(frame(7000))
    short = []
    Segmenter(Config(), short.append).flush()
    assert short == []
    tiny = Segmenter(Config(), short.append)
    tiny.push(frame(count=17))
    tiny.flush()
    assert short[0].final and short[0].frame.end_sample == 17


def test_frame_queue_never_waits_for_capacity_and_counts_dropped_audio():
    counters = Counters()
    queue = FrameQueue(2, counters)
    queue.put(frame())
    queue.put(frame(320))
    with pytest.raises(PipelineError, match="overflow"):
        queue.put(frame(640))
    stats = counters.snapshot()
    assert stats.audio_frames == 2 and stats.max_frame_backlog == 2
    assert stats.dropped_frames == 1 and stats.dropped_samples == 320
    assert queue.get().start_sample == 0
    with pytest.raises(PipelineError, match="bound"):
        queue.put(frame(count=481))


def test_pipeline_stats_publish_input_level_and_decoder_activity():
    counters = Counters()
    counters.set("input_level_dbfs", -18.5)
    counters.set("decoder_busy", True)

    stats = counters.snapshot()

    assert stats.input_level_dbfs == -18.5
    assert stats.decoder_busy


def test_eof_race_drains_last_frame_arriving_between_empty_read_and_producer_done(monkeypatch):
    queue = FrameQueue(2, Counters())
    done = Event()
    original_get = queue.get
    first = True

    def racing_get():
        nonlocal first
        if first:
            first = False
            queue.put(frame())  # Producer's last put, just after an Empty read.
            done.set()
            return None
        return original_get()

    monkeypatch.setattr(queue, "get", racing_get)
    last, drained = queue.next(done)
    assert not drained and last.start_sample == 0 and last.end_sample == 320
    assert queue.next(done) == (None, True)


def test_final_priority_partial_replacement_inflight_staleness_and_queue_bound():
    counters = Counters()
    queue = JobQueue(1, counters)
    queue.put(job())
    inflight = queue.get()
    queue.put(job(end=20000))
    assert queue.stale(inflight)
    queue.put(job(final=True))
    queue.put(job(number=2))
    assert queue.get().final
    assert queue.get().segment == 2
    queue.put(job(number=2, final=True))
    with pytest.raises(PipelineError, match="Final queue overflow"):
        queue.put(job(number=3, final=True))
    assert counters.snapshot().final_jobs_rejected == 1
    assert counters.snapshot().partial_jobs_dropped == 1
    assert counters.snapshot().max_job_backlog <= 2
    queue.finish(abort=True)
    assert queue.get() is None


def test_revisions_stable_prefix_final_once_and_monotonic_emission():
    times = iter([1, 2, 1.5, 3])
    stabilizer = Stabilizer("session", clock=lambda: next(times))
    first = job()
    e1 = stabilizer.accept(first, result(first, (0, 16000, "Jó napot")))
    later = job(end=24000)
    e2 = stabilizer.accept(later, result(later, (0, 24000, "Jó napot kívánok")))
    final = job(end=24000, final=True)
    e3 = stabilizer.accept(final, result(final, (0, 24000, "Jó napot kívánok.")))
    assert [e.revision for e in [e1, e2, e3]] == [1, 2, 3]
    assert e2.stable_prefix == "Jó napot"
    assert e1.emitted_monotonic_ms <= e2.emitted_monotonic_ms <= e3.emitted_monotonic_ms
    assert e1.segment_id == e3.segment_id and e3.type == "final"
    assert e3.confidence is None
    assert stabilizer.accept(final, result(final)) is None
    assert stabilizer.accept(first, result(first)) is None
    with pytest.raises(FrozenInstanceError):
        e3.text = "changed"


def test_rolling_overlap_dedup_and_final_preserves_real_repetition():
    stabilizer = Stabilizer("session")
    a = job(end=80000)
    assert stabilizer.accept(a, result(a, (0, 80000, "egy kettő három"))).text == "egy kettő három"
    b = job(start=12000, end=92000)
    assert stabilizer.accept(b, result(b, (12000, 92000, "kettő három négy"))).text == (
        "egy kettő három négy"
    )
    final = job(end=96000, final=True)
    event = stabilizer.accept(
        final, result(final, (0, 16000, "igen"), (16000, 32000, "igen"), (32000, 96000, "négy"))
    )
    assert event.text == "igen igen négy"  # Nonoverlapping repetition is real speech.


def test_overlapping_backend_duplicate_silence_and_new_session_are_isolated():
    stabilizer = Stabilizer("one")
    work = job()
    assert stabilizer.accept(work, result(work)) is None
    event = stabilizer.accept(work, result(work, (0, 10000, "igen"), (100, 12000, "igen")))
    assert event.text == "igen"
    final = replace(work, final=True)
    assert stabilizer.accept(final, result(final)).text == ""  # Clears a provisional hallucination.
    other = Stabilizer("two")
    event = other.accept(final, result(final, (0, 16000, "igen")))
    assert event.session_id == "two" and event.revision == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("partial_interval_ms", 0),
        ("frame_queue_capacity", 0),
        ("final_queue_capacity", 100),
        ("event_queue_capacity", True),
        ("stop_timeout_ms", 1),
    ],
)
def test_pipeline_configuration_bounds(field, value):
    with pytest.raises(ConfigError):
        Config(pipeline=replace(PipelineConfig(), **{field: value}))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -100.0])
def test_invalid_vad_threshold(value):
    with pytest.raises(ConfigError):
        Config(vad=replace(VadConfig(), energy_threshold_db=value))
