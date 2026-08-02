"""Bounded and non-blocking capture of merged process output."""

from __future__ import annotations

from collections import deque
from io import TextIOWrapper
from threading import Lock, Thread
from typing import BinaryIO


RETAINED_OUTPUT_LINES = 10
VISIBLE_OUTPUT_LINES = 5
OUTPUT_READER_JOIN_SECONDS = 2.0


class _RollingLineBuffer:
    """Keep only the newest output lines and count older discarded lines."""

    def __init__(self) -> None:
        self._lines: deque[str] = deque(maxlen=RETAINED_OUTPUT_LINES)
        self._discarded_line_count = 0
        self._lock = Lock()

    def append(self, line: str) -> None:
        """Append one complete or final unterminated output line."""
        with self._lock:
            if len(self._lines) == RETAINED_OUTPUT_LINES:
                self._discarded_line_count += 1
            self._lines.append(line)

    @property
    def retained_lines(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._lines)

    @property
    def visible_lines(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._lines)[-VISIBLE_OUTPUT_LINES:]

    @property
    def discarded_line_count(self) -> int:
        with self._lock:
            return self._discarded_line_count


class ProcessOutputCapture:
    """Drain and decode one merged binary process pipe on a reader thread."""

    def __init__(self, stream: BinaryIO) -> None:
        self._buffer = _RollingLineBuffer()
        self._stream = stream
        self._error: Exception | None = None
        self._thread = Thread(
            target=self._drain,
            name="patchharbor-output-reader",
            daemon=True,
        )
        self._started = False
        self._finished = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def retained_lines(self) -> tuple[str, ...]:
        """Return the at most ten lines retained in memory."""
        return self._buffer.retained_lines

    @property
    def visible_lines(self) -> tuple[str, ...]:
        """Return the last five lines for the current simple output."""
        return self._buffer.visible_lines

    @property
    def discarded_line_count(self) -> int:
        """Return how many older lines were evicted from the buffer."""
        return self._buffer.discarded_line_count

    def start(self) -> None:
        """Start draining before the child can fill its output pipe."""
        if self._started:
            raise RuntimeError("script output capture has already started")
        self._started = True
        self._thread.start()

    def finish(
        self,
        *,
        timeout_seconds: float = OUTPUT_READER_JOIN_SECONDS,
    ) -> None:
        """Wait for EOF and report reader or decoding failures."""
        if not self._started:
            raise RuntimeError("script output capture has not started")
        if not self._finished:
            self._thread.join(timeout=timeout_seconds)
            if self._thread.is_alive():
                raise OSError("script output reader did not finish")
            self._finished = True
        if self._error is not None:
            raise OSError(f"cannot read script output: {self._error}")

    def _drain(self) -> None:
        text_stream: TextIOWrapper | None = None
        try:
            text_stream = TextIOWrapper(
                self._stream,
                encoding="utf-8",
                errors="replace",
                newline=None,
            )
            for line in text_stream:
                self._buffer.append(line)
        except Exception as exc:  # reported by finish() on the controlling thread
            self._error = exc
        finally:
            try:
                if text_stream is None:
                    self._stream.close()
                else:
                    text_stream.close()
            except OSError as exc:
                if self._error is None:
                    self._error = exc
