"""Opt-in benchmark report schema and JSONL/CSV/Markdown export."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from offline_stt.metrics import (
    CriticalFieldScore,
    Distribution,
    ErrorRate,
    PipelineSummary,
)

_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    test_id: str
    hardware_category: str
    model_id: str
    model_revision: str
    model_sha256: str
    app_version: str
    operating_system: str
    cpu_model: str
    logical_cpu_count: int
    cpu_threads: int
    language: str
    started_utc: str
    parameters: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkMetrics:
    pipeline: PipelineSummary
    first_partial_latency_ms: Distribution = field(
        default_factory=lambda: Distribution(0, None, None, None)
    )
    first_final_latency_ms: Distribution = field(
        default_factory=lambda: Distribution(0, None, None, None)
    )
    vad_endpoint_latency_ms: Distribution = field(
        default_factory=lambda: Distribution(0, None, None, None)
    )
    wer: ErrorRate | None = None
    cer: ErrorRate | None = None
    critical_fields: CriticalFieldScore | None = None
    average_cpu_percent: float | None = None
    peak_working_set_bytes: int | None = None
    process_sample_count: int = 0


@dataclass(frozen=True)
class TranscriptRow:
    utterance_id: str
    reference: str
    hypothesis: str


@dataclass(frozen=True)
class BenchmarkReport:
    metadata: RunMetadata
    metrics: BenchmarkMetrics
    transcripts: tuple[TranscriptRow, ...] = ()


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _flatten(value: Any, prefix: str = "") -> dict[str, object]:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, nested in sorted(value.items()):
            name = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(nested, name))
        return result
    return {prefix: value}


def _record(report: BenchmarkReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "metadata": asdict(report.metadata),
        "metrics": asdict(report.metrics),
    }


def _markdown(record: dict[str, object]) -> str:
    rows = _flatten(record)
    lines = [
        "# RoboAssist benchmark riport",
        "",
        "Ez a futás összesített metrikáit tartalmazza. A riport önmagában nem jelent",
        "reprodukálható benchmarkot; ehhez a hangforrás, licenc és futási protokoll is kell.",
        "",
        "| Mező | Érték |",
        "|---|---|",
    ]
    for key, value in rows.items():
        rendered = _json_text(value) if isinstance(value, (dict, list)) else str(value)
        safe_value = rendered.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{key}` | {safe_value} |")
    return "\n".join(lines) + "\n"


def export_report(
    report: BenchmarkReport,
    output_parent: str | Path,
    *,
    include_transcript: bool = False,
) -> Path:
    """Write one report to a new run directory; transcript export requires opt-in.

    The caller must provide an output location explicitly. Existing run folders
    are never overwritten. JSONL/CSV/Markdown contain aggregate metrics only;
    raw reference and hypothesis text is written to a separate JSONL file only
    when ``include_transcript`` is true.
    """
    run_id = report.metadata.run_id
    if _RUN_ID.fullmatch(run_id) is None:
        raise ValueError("run_id must be a simple identifier, not a path")
    if report.metadata.logical_cpu_count < 1 or report.metadata.cpu_threads < 1:
        raise ValueError("CPU counts must be positive")
    if report.metrics.process_sample_count < 0:
        raise ValueError("process_sample_count cannot be negative")
    cpu = report.metrics.average_cpu_percent
    if cpu is not None and (not math.isfinite(cpu) or not 0 <= cpu <= 100):
        raise ValueError("average_cpu_percent must be finite and within total machine capacity")
    working_set = report.metrics.peak_working_set_bytes
    if working_set is not None and working_set < 0:
        raise ValueError("peak_working_set_bytes cannot be negative")
    if (cpu is not None or working_set is not None) and report.metrics.process_sample_count == 0:
        raise ValueError("process metrics require at least one process sample")

    record = _record(report)
    record_line = _json_text(record) + "\n"
    flattened = _flatten(record)
    headers = list(flattened)
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=headers, extrasaction="raise")
    writer.writeheader()
    writer.writerow(flattened)
    csv_text = csv_buffer.getvalue()
    markdown = _markdown(record)

    transcript_text = "".join(
        _json_text(
            {
                "schema_version": 1,
                "utterance_id": row.utterance_id,
                "reference": row.reference,
                "hypothesis": row.hypothesis,
            }
        )
        + "\n"
        for row in report.transcripts
    )

    parent = Path(output_parent)
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / run_id
    if destination.exists():
        raise FileExistsError(f"Report already exists: {destination}")

    stage = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=parent))
    try:
        (stage / "summary.jsonl").write_text(record_line, encoding="utf-8", newline="\n")
        (stage / "summary.csv").write_text(csv_text, encoding="utf-8", newline="")
        (stage / "summary.md").write_text(markdown, encoding="utf-8", newline="\n")
        if include_transcript:
            (stage / "transcripts.jsonl").write_text(
                transcript_text, encoding="utf-8", newline="\n"
            )
        os.rename(stage, destination)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return destination
