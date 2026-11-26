from offline_stt.pipeline.types import TranscriptEvent
from offline_stt.ui.transcript import TranscriptBuffer


def event(
    *,
    segment="session:1",
    revision=1,
    kind="partial",
    text="Jó napot",
    start=0.0,
):
    return TranscriptEvent(
        1,
        "session",
        segment,
        revision,
        "microphone",
        "hu",
        kind,
        start,
        start + 1000,
        text,
        1000.0,
    )


def test_partial_revisions_replace_and_final_is_immutable():
    buffer = TranscriptBuffer()

    assert buffer.accept(event(revision=1, text="Jó nap"))
    assert buffer.accept(event(revision=2, text="Jó napot"))
    assert not buffer.accept(event(revision=1, text="régi szöveg"))
    assert buffer.accept(event(revision=3, kind="final", text="Jó napot kívánok"))
    assert not buffer.accept(event(revision=4, text="új partial"))
    assert buffer.plain_text == "Jó napot kívánok"
    assert buffer.parts == (("Jó napot kívánok", True),)


def test_clear_ignores_later_updates_for_visible_segments():
    buffer = TranscriptBuffer()
    buffer.accept(event())

    buffer.clear_visible()

    assert buffer.is_empty
    assert not buffer.accept(event(revision=2, text="törölt szöveg"))
    assert buffer.accept(event(segment="session:2", start=1000.0, text="Új mondat"))
    assert buffer.plain_text == "Új mondat"


def test_session_end_removes_all_text_and_ignore_state():
    buffer = TranscriptBuffer()
    buffer.accept(event())
    buffer.clear_visible()
    buffer.end_session()

    assert buffer.is_empty
    assert buffer.accept(event(revision=2, text="új session"))


def test_transcript_memory_limit_discards_oldest_segments():
    buffer = TranscriptBuffer(max_segments=2, max_characters=100)
    buffer.accept(event(segment="session:1", text="Első", start=0))
    buffer.accept(event(segment="session:2", text="Második", start=1000))
    buffer.accept(event(segment="session:3", text="Harmadik", start=2000))

    assert buffer.parts == (("Második", False), ("Harmadik", False))
    assert buffer.truncated
