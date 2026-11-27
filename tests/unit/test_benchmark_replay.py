import json

import pytest
from PySide6.QtWidgets import QApplication

from offline_stt.benchmark_replay import ReplayBenchmarkWindow, load_annotations
from offline_stt.benchmark_report import RunMetadata
from offline_stt.pipeline.types import PipelineStats, SessionState, TranscriptEvent


class FakeSession:
    state = SessionState.IDLE
    error = None
    stats = PipelineStats()

    def __init__(self):
        self.closed = False

    def drain_events(self):
        return ()

    def wait(self, _timeout=0):
        return False

    def close(self):
        self.closed = True
        self.state = SessionState.CLOSED


class FakeSampler:
    def sample(self):
        return None


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


def _metadata():
    return RunMetadata(
        run_id="test-replay",
        test_id="synthetic-test",
        hardware_category="test",
        model_id="base-multilingual",
        model_revision="revision",
        model_sha256="0" * 64,
        app_version="0.1.0",
        operating_system="Windows test",
        cpu_model="Synthetic CPU",
        logical_cpu_count=8,
        cpu_threads=2,
        language="hu",
        started_utc="2026-11-27T00:00:00Z",
    )


def test_load_annotations_accepts_hungarian_text_and_typed_fields(tmp_path):
    path = tmp_path / "annotations.jsonl"
    path.write_text(
        json.dumps(
            {
                "utterance_id": "u1",
                "speech_start_ms": 25,
                "speech_end_ms": 1200,
                "reference_text": "Árpád hívjon 1234,50",
                "critical_fields": {
                    "name": {"value": "Árpád", "kind": "text"},
                    "amount": {"value": "1234,50", "kind": "decimal"},
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    annotations = load_annotations(path)

    assert annotations[0].reference_text == "Árpád hívjon 1234,50"
    assert annotations[0].critical_fields == {
        "name": ("Árpád", "text"),
        "amount": ("1234,50", "decimal"),
    }


def test_load_annotations_rejects_unknown_field_kind(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "utterance_id": "u1",
                "speech_start_ms": 0,
                "speech_end_ms": 100,
                "reference_text": "teszt",
                "critical_fields": {"value": {"value": "1", "kind": "unknown"}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="critical field"):
        load_annotations(path)


def test_replay_window_records_text_after_actual_transcript_paint(qt_app, tmp_path):
    session = FakeSession()
    window = ReplayBenchmarkWindow(
        session, (), _metadata(), tmp_path, include_transcript=False, sampler=FakeSampler()
    )
    event = TranscriptEvent(
        1, "session", "session:1", 1, "wav", "hu", "final", 0, 1000, "Jó napot", 10
    )
    try:
        window.show()
        qt_app.processEvents()
        assert window._buffer.accept(event)
        window._pending[event.segment_id] = event
        window._transcript.render_buffer(window._buffer)
        window._transcript.repaint()
        qt_app.processEvents()

        assert len(window._presentations) == 1
        assert window._presentations[0].event == event
        assert window._presentations[0].displayed_monotonic_ns > 0
    finally:
        window.close()
        qt_app.processEvents()
    assert session.closed
