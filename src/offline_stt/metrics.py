"""Deterministic, privacy-neutral benchmark calculations.

This module only computes values. It never reads audio, writes transcripts, or
starts measurement automatically; callers decide when to collect and export.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, TypeVar

from offline_stt.pipeline.types import PipelineStats, TranscriptEvent

T = TypeVar("T")
CriticalKind = Literal["text", "integer", "decimal", "identifier"]


@dataclass(frozen=True)
class ErrorRate:
    errors: int
    reference_units: int
    rate: float | None


@dataclass(frozen=True)
class Distribution:
    count: int
    p50: float | None
    p95: float | None
    p99: float | None


@dataclass(frozen=True)
class CriticalFieldScore:
    correct: int
    total: int
    accuracy: float | None


@dataclass(frozen=True)
class PipelineSummary:
    audio_seconds: float | None
    decode_seconds: float
    rtf: float | None
    decoded_audio_seconds: float
    repeated_decode_seconds: float
    repeated_decode_fraction: float | None
    partial_decode_seconds: float
    final_decode_seconds: float
    max_frame_backlog: int
    max_job_backlog: int
    dropped_frames: int
    dropped_samples: int
    partial_jobs_dropped: int
    final_jobs_rejected: int


@dataclass(frozen=True)
class UtteranceAnnotation:
    utterance_id: str
    speech_start_ms: float
    speech_end_ms: float
    reference_text: str
    critical_fields: dict[str, tuple[str, CriticalKind]]


@dataclass(frozen=True)
class EventPresentation:
    event: TranscriptEvent
    displayed_monotonic_ns: int


@dataclass(frozen=True)
class UtteranceEvaluation:
    utterance_id: str
    reference_text: str
    hypothesis_text: str
    word_errors: int
    reference_words: int
    character_errors: int
    reference_characters: int
    first_partial_latency_ms: float | None
    first_final_latency_ms: float | None
    vad_endpoint_latency_ms: float | None
    critical_correct: int
    critical_total: int


@dataclass(frozen=True)
class EvaluationSummary:
    utterances: tuple[UtteranceEvaluation, ...]
    wer: ErrorRate
    cer: ErrorRate
    critical_fields: CriticalFieldScore
    first_partial_latency_ms: Distribution
    first_final_latency_ms: Distribution
    vad_endpoint_latency_ms: Distribution


def normalize_text(text: str) -> str:
    """Case-fold and remove punctuation while preserving accents and digits.

    Unicode letters, numbers, and combining marks are retained. Punctuation,
    symbols, and whitespace become a single word boundary; diacritics are never
    stripped. CER uses this same normalized form, including collapsed spaces.
    """
    normalized = unicodedata.normalize("NFC", text).casefold()
    result: list[str] = []
    separator = True
    for char in normalized:
        category = unicodedata.category(char)
        if char.isspace() or category[0] in ("P", "S"):
            if not separator:
                result.append(" ")
            separator = True
        else:
            result.append(char)
            separator = False
    if result and result[-1] == " ":
        result.pop()
    return "".join(result)


def normalize_critical_value(value: str, kind: CriticalKind) -> str:
    """Normalize one annotated field using its declared semantic kind.

    Integer and identifier fields compare digits and a leading sign, ignoring
    visual separators. Decimal fields accept comma or dot as the decimal mark;
    if both appear, the last separator is decimal and the others are grouping.
    """
    if kind not in ("text", "integer", "decimal", "identifier"):
        raise ValueError(f"Unsupported critical field kind: {kind}")
    if kind == "text":
        return normalize_text(value)
    normalized = unicodedata.normalize("NFC", value).casefold()
    sign = "-" if normalized.lstrip().startswith(("-", "−")) else ""
    digits = "".join(str(unicodedata.decimal(char)) for char in normalized if char.isdecimal())
    if not digits:
        return sign
    if kind in ("integer", "identifier"):
        return sign + digits
    if kind != "decimal":
        raise ValueError(f"Unsupported critical field kind: {kind}")

    separators = [(index, char) for index, char in enumerate(normalized) if char in ",."]
    if not separators:
        return sign + digits
    decimal_index = separators[-1][0]
    before = "".join(
        str(unicodedata.decimal(char)) for char in normalized[:decimal_index] if char.isdecimal()
    )
    after = "".join(
        str(unicodedata.decimal(char))
        for char in normalized[decimal_index + 1 :]
        if char.isdecimal()
    )
    if not before:
        before = "0"
    if not after:
        return sign + before
    after = after.rstrip("0")
    if not after:
        return sign + before
    return f"{sign}{before}.{after}"


def edit_distance(reference: Sequence[T], hypothesis: Sequence[T]) -> int:
    """Return Levenshtein distance in O(min(n, m)) memory."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for row, left in enumerate(reference, start=1):
        current = [row]
        for column, right in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def _error_rate(reference: Sequence[T], hypothesis: Sequence[T]) -> ErrorRate:
    errors = edit_distance(reference, hypothesis)
    units = len(reference)
    return ErrorRate(errors, units, errors / units if units else None)


def word_error_rate(reference: str, hypothesis: str) -> ErrorRate:
    """Compute WER after case/punctuation normalization, keeping accents."""
    return _error_rate(normalize_text(reference).split(), normalize_text(hypothesis).split())


def character_error_rate(reference: str, hypothesis: str) -> ErrorRate:
    """Compute CER over normalized characters, including one space between words."""
    return _error_rate(normalize_text(reference), normalize_text(hypothesis))


def critical_field_score(
    reference: dict[str, tuple[str, CriticalKind]],
    hypothesis: dict[str, str],
) -> CriticalFieldScore:
    """Score annotated critical values exactly after kind-specific normalization."""
    if not reference:
        return CriticalFieldScore(0, 0, None)
    correct = 0
    for name, (expected, kind) in reference.items():
        if not expected.strip():
            raise ValueError(f"Critical field reference {name!r} cannot be empty")
        actual = hypothesis.get(name, "")
        if normalize_critical_value(expected, kind) == normalize_critical_value(actual, kind):
            correct += 1
    return CriticalFieldScore(correct, len(reference), correct / len(reference))


def _critical_value_in_text(hypothesis: str, expected: str, kind: CriticalKind) -> bool:
    if kind == "text":
        words = normalize_text(expected).split()
        actual = normalize_text(hypothesis).split()
        if not words:
            return False
        return any(actual[index : index + len(words)] == words for index in range(len(actual)))
    candidates = re.findall(r"(?<!\w)[+\-−]?\d+(?:[\s,./\-]*\d+)*(?!\w)", hypothesis)
    target = normalize_critical_value(expected, kind)
    return any(normalize_critical_value(candidate, kind) == target for candidate in candidates)


def evaluate_annotations(
    annotations: Sequence[UtteranceAnnotation],
    presentations: Sequence[EventPresentation],
    *,
    source_started_monotonic_ns: int,
) -> EvaluationSummary:
    """Compare final painted UI events with annotated utterances in memory.

    Latencies use the source's monotonic start as the wall-clock equivalent of
    audio time zero. VAD endpoint latency remains on the audio timeline and is
    intentionally reported separately. This function persists no text.
    """
    if source_started_monotonic_ns < 0:
        raise ValueError("Source monotonic start must be nonnegative")
    seen: set[str] = set()
    results: list[UtteranceEvaluation] = []
    word_errors = word_count = character_errors = character_count = 0
    critical_correct = critical_total = 0
    partial_latencies: list[float] = []
    final_latencies: list[float] = []
    vad_latencies: list[float] = []

    for annotation in annotations:
        if (
            not annotation.utterance_id
            or annotation.utterance_id in seen
            or not math.isfinite(annotation.speech_start_ms)
            or not math.isfinite(annotation.speech_end_ms)
            or annotation.speech_start_ms < 0
            or annotation.speech_end_ms <= annotation.speech_start_ms
        ):
            raise ValueError("Utterance annotations need unique IDs and valid speech bounds")
        seen.add(annotation.utterance_id)
        relevant = [
            presentation
            for presentation in presentations
            if presentation.event.audio_start_ms <= annotation.speech_end_ms
            and presentation.event.audio_end_ms >= annotation.speech_start_ms
        ]
        partials = [item for item in relevant if item.event.type == "partial"]
        finals = [item for item in relevant if item.event.type == "final"]
        selected_finals = sorted(
            finals, key=lambda item: (item.event.audio_start_ms, item.event.audio_end_ms)
        )
        hypothesis = " ".join(item.event.text for item in selected_finals).strip()
        first_partial = min(partials, key=lambda item: item.displayed_monotonic_ns, default=None)
        first_final = min(finals, key=lambda item: item.displayed_monotonic_ns, default=None)
        display_zero_ms = source_started_monotonic_ns / 1_000_000
        partial_latency = (
            first_partial.displayed_monotonic_ns / 1_000_000
            - display_zero_ms
            - annotation.speech_start_ms
            if first_partial is not None
            else None
        )
        final_latency = (
            first_final.displayed_monotonic_ns / 1_000_000
            - display_zero_ms
            - annotation.speech_end_ms
            if first_final is not None
            else None
        )
        vad_latency = (
            max(item.event.audio_end_ms for item in selected_finals) - annotation.speech_end_ms
            if selected_finals
            else None
        )
        word_rate = word_error_rate(annotation.reference_text, hypothesis)
        char_rate = character_error_rate(annotation.reference_text, hypothesis)
        fields = {
            name: _critical_value_in_text(hypothesis, expected, kind)
            for name, (expected, kind) in annotation.critical_fields.items()
        }
        field_correct = sum(fields.values())
        field_total = len(fields)
        word_errors += word_rate.errors
        word_count += word_rate.reference_units
        character_errors += char_rate.errors
        character_count += char_rate.reference_units
        critical_correct += field_correct
        critical_total += field_total
        if partial_latency is not None:
            partial_latencies.append(partial_latency)
        if final_latency is not None:
            final_latencies.append(final_latency)
        if vad_latency is not None:
            vad_latencies.append(vad_latency)
        results.append(
            UtteranceEvaluation(
                annotation.utterance_id,
                annotation.reference_text,
                hypothesis,
                word_rate.errors,
                word_rate.reference_units,
                char_rate.errors,
                char_rate.reference_units,
                partial_latency,
                final_latency,
                vad_latency,
                field_correct,
                field_total,
            )
        )

    return EvaluationSummary(
        tuple(results),
        ErrorRate(word_errors, word_count, word_errors / word_count if word_count else None),
        ErrorRate(
            character_errors,
            character_count,
            character_errors / character_count if character_count else None,
        ),
        CriticalFieldScore(
            critical_correct,
            critical_total,
            critical_correct / critical_total if critical_total else None,
        ),
        percentile_summary(partial_latencies),
        percentile_summary(final_latencies),
        percentile_summary(vad_latencies),
    )


def percentile_summary(values: Sequence[float]) -> Distribution:
    """Return nearest-rank p50/p95/p99 and sample count; empty input is undefined."""
    checked = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in checked):
        raise ValueError("Percentile samples must be finite")
    if not checked:
        return Distribution(0, None, None, None)

    def nearest_rank(percentile: float) -> float:
        rank = max(1, math.ceil(percentile * len(checked)))
        return checked[rank - 1]

    return Distribution(len(checked), nearest_rank(0.50), nearest_rank(0.95), nearest_rank(0.99))


def summarize_pipeline(stats: PipelineStats, *, sample_rate: int = 16_000) -> PipelineSummary:
    """Derive replay-normalized RTF and report repeated work/backlog separately."""
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive")
    nonnegative = (
        stats.audio_frames,
        stats.audio_samples,
        stats.dropped_frames,
        stats.dropped_samples,
        stats.max_frame_backlog,
        stats.frame_backlog,
        stats.max_job_backlog,
        stats.job_backlog,
        stats.partial_jobs_dropped,
        stats.final_jobs_rejected,
        stats.partial_decodes,
        stats.final_decodes,
        stats.engine_model_loads,
        stats.engine_warmup_calls,
        stats.decoded_audio_samples,
        stats.repeated_decode_samples,
        stats.partial_decode_seconds,
        stats.final_decode_seconds,
        stats.forced_terminations,
        stats.output_partial_dropped,
        stats.output_final_failures,
    )
    if any(not math.isfinite(float(value)) or value < 0 for value in nonnegative):
        raise ValueError("Pipeline counters must be finite and nonnegative")
    audio_seconds = stats.audio_samples / sample_rate if stats.audio_samples else None
    decode_seconds = stats.partial_decode_seconds + stats.final_decode_seconds
    decoded_audio_seconds = stats.decoded_audio_samples / sample_rate
    repeated_decode_seconds = stats.repeated_decode_samples / sample_rate
    return PipelineSummary(
        audio_seconds=audio_seconds,
        decode_seconds=decode_seconds,
        rtf=decode_seconds / audio_seconds if audio_seconds else None,
        decoded_audio_seconds=decoded_audio_seconds,
        repeated_decode_seconds=repeated_decode_seconds,
        repeated_decode_fraction=(
            stats.repeated_decode_samples / stats.decoded_audio_samples
            if stats.decoded_audio_samples
            else None
        ),
        partial_decode_seconds=stats.partial_decode_seconds,
        final_decode_seconds=stats.final_decode_seconds,
        max_frame_backlog=stats.max_frame_backlog,
        max_job_backlog=stats.max_job_backlog,
        dropped_frames=stats.dropped_frames,
        dropped_samples=stats.dropped_samples,
        partial_jobs_dropped=stats.partial_jobs_dropped,
        final_jobs_rejected=stats.final_jobs_rejected,
    )
