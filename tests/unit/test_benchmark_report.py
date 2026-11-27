import csv
import json

import pytest

from offline_stt.benchmark_report import (
    BenchmarkMetrics,
    BenchmarkReport,
    RunMetadata,
    TranscriptRow,
    export_report,
)
from offline_stt.metrics import (
    CriticalFieldScore,
    Distribution,
    character_error_rate,
    summarize_pipeline,
    word_error_rate,
)
from offline_stt.pipeline.types import PipelineStats


def _report(run_id="synthetic-001"):
    return BenchmarkReport(
        metadata=RunMetadata(
            run_id=run_id,
            test_id="synthetic-hu-v1",
            hardware_category="test",
            model_id="base-multilingual",
            model_revision="rev-test",
            model_sha256="0" * 64,
            app_version="0.1.0",
            operating_system="Windows test",
            cpu_model="Synthetic CPU",
            logical_cpu_count=8,
            cpu_threads=2,
            language="hu",
            started_utc="2026-11-27T00:00:00Z",
            parameters={"frame_ms": 20, "vad_threshold_db": -42.0},
        ),
        metrics=BenchmarkMetrics(
            pipeline=summarize_pipeline(
                PipelineStats(audio_samples=16_000, final_decode_seconds=0.5)
            ),
            first_partial_latency_ms=Distribution(1, 400, 400, 400),
            wer=word_error_rate("jó napot", "jó nap"),
            cer=character_error_rate("jó napot", "jó nap"),
            critical_fields=CriticalFieldScore(1, 1, 1.0),
            average_cpu_percent=12.5,
            peak_working_set_bytes=100_000_000,
            process_sample_count=3,
        ),
        transcripts=(TranscriptRow("u1", "Ügyfélszöveg", "PRIVÁT ÁTIRAT"),),
    )


def test_report_exports_aggregate_formats_without_transcript_by_default(tmp_path):
    output = export_report(_report(), tmp_path)
    assert output == tmp_path / "synthetic-001"
    assert sorted(path.name for path in output.iterdir()) == [
        "summary.csv",
        "summary.jsonl",
        "summary.md",
    ]
    jsonl = (output / "summary.jsonl").read_text(encoding="utf-8")
    record = json.loads(jsonl)
    assert record["metadata"]["run_id"] == "synthetic-001"
    assert record["metrics"]["pipeline"]["rtf"] == 0.5
    assert "PRIVÁT ÁTIRAT" not in jsonl
    assert "transcripts.jsonl" not in [path.name for path in output.iterdir()]

    with (output / "summary.csv").open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["metrics.pipeline.rtf"] == "0.5"
    assert row["metadata.logical_cpu_count"] == "8"
    assert "PRIVÁT ÁTIRAT" not in (output / "summary.csv").read_text(encoding="utf-8")
    assert "| `metadata.run_id` | synthetic-001 |" in (output / "summary.md").read_text(
        encoding="utf-8"
    )


def test_transcript_export_requires_explicit_opt_in(tmp_path):
    report = _report("with-transcript")
    output = export_report(report, tmp_path, include_transcript=True)
    transcript_lines = (output / "transcripts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(transcript_lines) == 1
    assert json.loads(transcript_lines[0])["hypothesis"] == "PRIVÁT ÁTIRAT"


def test_report_never_overwrites_and_rejects_path_like_run_ids(tmp_path):
    output = export_report(_report("fixed-run"), tmp_path)
    before = (output / "summary.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        export_report(_report("fixed-run"), tmp_path)
    assert (output / "summary.jsonl").read_bytes() == before
    with pytest.raises(ValueError, match="not a path"):
        export_report(_report("../outside"), tmp_path)


def test_process_metrics_require_samples_and_valid_machine_normalized_cpu(tmp_path):
    report = _report("without-samples")
    report = BenchmarkReport(
        metadata=report.metadata,
        metrics=BenchmarkMetrics(
            pipeline=report.metrics.pipeline,
            average_cpu_percent=5.0,
            process_sample_count=0,
        ),
    )
    with pytest.raises(ValueError, match="at least one process sample"):
        export_report(report, tmp_path)

    report = _report("over-capacity")
    report = BenchmarkReport(
        metadata=report.metadata,
        metrics=BenchmarkMetrics(
            pipeline=report.metrics.pipeline,
            average_cpu_percent=101.0,
            process_sample_count=1,
        ),
    )
    with pytest.raises(ValueError, match="total machine capacity"):
        export_report(report, tmp_path)
