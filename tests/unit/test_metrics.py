import math

import pytest

from offline_stt.metrics import (
    EventPresentation,
    UtteranceAnnotation,
    character_error_rate,
    critical_field_score,
    edit_distance,
    evaluate_annotations,
    normalize_critical_value,
    normalize_text,
    percentile_summary,
    summarize_pipeline,
    word_error_rate,
)
from offline_stt.pipeline.types import PipelineStats, TranscriptEvent


def test_text_normalization_preserves_hungarian_diacritics_and_discards_punctuation():
    assert normalize_text("ÁRVÍZ-tűrő, tükörfúrógép!") == "árvíz tűrő tükörfúrógép"
    assert word_error_rate("Árvíz-tűrő tükörfúrógép!", "árvíz tűrő tükörfúrógép").rate == 0
    assert word_error_rate("egy tűz", "egy tiz").rate == 0.5
    assert character_error_rate("Árvíz!", "árvíz").rate == 0


def test_edit_distance_and_empty_reference_are_explicit():
    assert edit_distance("kitten", "sitting") == 3
    assert word_error_rate("", "egy szó").rate is None
    assert word_error_rate("egy szó", "").errors == 2


def test_critical_fields_use_declared_text_number_and_identifier_rules():
    reference = {
        "name": ("Árpád utca", "text"),
        "phone": ("06-30-123-4567", "identifier"),
        "amount": ("1 234,50 Ft", "decimal"),
    }
    hypothesis = {
        "name": "árpád, utca",
        "phone": "(06) 30 123 4567",
        "amount": "1234.50",
    }
    score = critical_field_score(reference, hypothesis)
    assert (score.correct, score.total, score.accuracy) == (3, 3, 1)
    assert normalize_critical_value("1 234,50 Ft", "decimal") == "1234.5"
    assert normalize_critical_value("06-30-123-4567", "identifier") == "06301234567"
    assert normalize_critical_value("1234,500", "decimal") == "1234.5"


def test_critical_field_rejects_empty_references_and_missing_hypotheses():
    with pytest.raises(ValueError, match="cannot be empty"):
        critical_field_score({"name": ("", "text")}, {"name": ""})
    with pytest.raises(ValueError, match="Unsupported"):
        normalize_critical_value("x", "unknown")  # type: ignore[arg-type]
    score = critical_field_score({"account": ("007", "integer")}, {})
    assert (score.correct, score.total, score.accuracy) == (0, 1, 0)
    assert critical_field_score({}, {}).accuracy is None


def test_percentiles_use_nearest_rank_and_report_count():
    summary = percentile_summary([10, 2, 1, 8, 5, 4, 3, 9, 6, 7])
    assert (summary.count, summary.p50, summary.p95, summary.p99) == (10, 5, 10, 10)
    assert percentile_summary([]).p95 is None
    with pytest.raises(ValueError, match="finite"):
        percentile_summary([1, math.inf])


def test_pipeline_summary_counts_repeated_decode_work_without_hiding_it_in_rtf():
    summary = summarize_pipeline(
        PipelineStats(
            audio_samples=16_000,
            decoded_audio_samples=48_000,
            repeated_decode_samples=16_000,
            partial_decode_seconds=1.0,
            final_decode_seconds=0.5,
            max_frame_backlog=4,
            max_job_backlog=2,
            dropped_frames=1,
            dropped_samples=480,
            partial_jobs_dropped=3,
            final_jobs_rejected=0,
        )
    )
    assert summary.audio_seconds == 1
    assert summary.decode_seconds == 1.5
    assert summary.rtf == 1.5
    assert summary.decoded_audio_seconds == 3
    assert summary.repeated_decode_seconds == 1
    assert summary.repeated_decode_fraction == pytest.approx(1 / 3)
    assert (summary.max_frame_backlog, summary.max_job_backlog) == (4, 2)
    assert (summary.dropped_frames, summary.dropped_samples) == (1, 480)


def test_pipeline_summary_marks_empty_rtf_and_validates_inputs():
    assert summarize_pipeline(PipelineStats()).rtf is None
    with pytest.raises(ValueError, match="Sample rate"):
        summarize_pipeline(PipelineStats(), sample_rate=0)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        summarize_pipeline(PipelineStats(dropped_frames=-1))


def test_annotation_evaluation_measures_ui_latency_vad_and_quality_separately():
    annotation = UtteranceAnnotation(
        "utterance-1",
        1000,
        2000,
        "Árpád hívjon 1234,50",
        {"name": ("Árpád", "text"), "amount": ("1234,50", "decimal")},
    )
    partial = TranscriptEvent(
        1, "session", "segment-1", 1, "wav", "hu", "partial", 900, 1600, "Árpád hívjon", 1
    )
    final = TranscriptEvent(
        1,
        "session",
        "segment-1",
        2,
        "wav",
        "hu",
        "final",
        900,
        2100,
        "Árpád hívjon 1234.50",
        2,
    )
    result = evaluate_annotations(
        [annotation],
        [
            EventPresentation(partial, 2_400_000_000),
            EventPresentation(final, 3_250_000_000),
        ],
        source_started_monotonic_ns=1_000_000_000,
    )
    assert result.wer.rate == 0
    assert result.cer.rate == 0
    assert result.critical_fields.accuracy == 1
    assert result.first_partial_latency_ms.p50 == 400
    assert result.first_final_latency_ms.p50 == 250
    assert result.vad_endpoint_latency_ms.p50 == 100
    assert result.utterances[0].hypothesis_text == "Árpád hívjon 1234.50"


def test_annotation_evaluation_keeps_missing_final_and_empty_samples_visible():
    annotation = UtteranceAnnotation("u1", 0, 1000, "beszéd itt", {})
    result = evaluate_annotations([annotation], [], source_started_monotonic_ns=0)
    assert result.wer.rate == 1
    assert result.first_partial_latency_ms.count == 0
    assert result.first_final_latency_ms.count == 0
    assert result.vad_endpoint_latency_ms.count == 0
    assert result.critical_fields.accuracy is None

    with pytest.raises(ValueError, match="unique IDs"):
        evaluate_annotations([annotation, annotation], [], source_started_monotonic_ns=0)
