"""Small in-memory transcript view model with explicit session clearing."""

from __future__ import annotations

from dataclasses import dataclass

from offline_stt.pipeline.types import TranscriptEvent


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: float
    revision: int
    final: bool
    text: str


class TranscriptBuffer:
    """Keep revisions in memory; never writes transcript text to disk."""

    def __init__(self, *, max_segments: int = 2000, max_characters: int = 100_000) -> None:
        if max_segments < 1 or max_characters < 1:
            raise ValueError("Transcript memory limits must be positive")
        self._max_segments = max_segments
        self._max_characters = max_characters
        self._segments: dict[str, TranscriptSegment] = {}
        self._ignored_segments: set[str] = set()
        self._truncated = False

    def begin_session(self) -> None:
        self._segments.clear()
        self._ignored_segments.clear()
        self._truncated = False

    def accept(self, event: TranscriptEvent) -> bool:
        if event.segment_id in self._ignored_segments:
            return False
        previous = self._segments.get(event.segment_id)
        if previous is not None and (previous.final or event.revision <= previous.revision):
            return False
        self._segments[event.segment_id] = TranscriptSegment(
            event.audio_start_ms,
            event.revision,
            event.type == "final",
            " ".join(event.text.split()),
        )
        self._trim()
        return True

    def _trim(self) -> None:
        text_size = sum(len(segment.text) for segment in self._segments.values())
        while self._segments and (
            len(self._segments) > self._max_segments or text_size > self._max_characters
        ):
            oldest_id = min(self._segments, key=lambda key: self._segments[key].start_ms)
            removed = self._segments.pop(oldest_id)
            text_size -= len(removed.text)
            self._truncated = True

    def clear_visible(self) -> None:
        """Clear current text and ignore later revisions of those same live segments."""
        self._ignored_segments.update(self._segments)
        self._segments.clear()
        self._truncated = False

    def end_session(self) -> None:
        self._segments.clear()
        self._ignored_segments.clear()
        self._truncated = False

    @property
    def is_empty(self) -> bool:
        return not self._segments

    @property
    def truncated(self) -> bool:
        return self._truncated

    @property
    def parts(self) -> tuple[tuple[str, bool], ...]:
        ordered = sorted(self._segments.values(), key=lambda item: item.start_ms)
        return tuple((item.text, item.final) for item in ordered if item.text)

    @property
    def plain_text(self) -> str:
        return " ".join(text for text, _ in self.parts)
