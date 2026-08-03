"""Bounded output capture and explicit output target routing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from io import BufferedReader, RawIOBase, TextIOWrapper
from threading import Lock, Thread
from typing import BinaryIO, Callable, TextIO


RETAINED_OUTPUT_LINES = 10
VISIBLE_OUTPUT_LINES = 5
OUTPUT_READER_JOIN_SECONDS = 2.0


@dataclass(frozen=True)
class OutputTargets:
    """Destinations for bounded, plain, and byte-exact process output."""

    bounded_text_stream: TextIO
    plain_text_stream: TextIO | None = None
    raw_output_stream: BinaryIO | None = None

    @property
    def live_text_streams(self) -> tuple[TextIO, ...]:
        """Return destinations that receive every decoded line."""
        if self.plain_text_stream is None:
            return ()
        return (self.plain_text_stream,)

    @property
    def raw_byte_streams(self) -> tuple[BinaryIO, ...]:
        """Return destinations that receive the original process bytes."""
        if self.raw_output_stream is None:
            return ()
        return (self.raw_output_stream,)

    def write_visible_lines(self, lines: tuple[str, ...]) -> None:
        """Write the bounded view unless plain streaming is active."""
        if self.plain_text_stream is not None:
            return
        for line in lines:
            self.bounded_text_stream.write(line)
        self.bounded_text_stream.flush()


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


class _RawOutputTee(RawIOBase):
    """Copy source bytes to raw sinks before text decoding."""

    def __init__(
        self,
        source: BinaryIO,
        destinations: tuple[BinaryIO, ...],
        remember_error: Callable[[str, Exception], None],
    ) -> None:
        super().__init__()
        self._source = source
        self._destinations = list(dict.fromkeys(destinations))
        self._remember_error = remember_error

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray | memoryview) -> int | None:
        reader = getattr(self._source, "read1", self._source.read)
        chunk = reader(len(buffer))
        if chunk is None:
            return None
        if not chunk:
            return 0

        view = memoryview(buffer)
        view[: len(chunk)] = chunk
        active_destinations: list[BinaryIO] = []
        for destination in self._destinations:
            try:
                written = destination.write(chunk)
                if written is not None and written != len(chunk):
                    raise OSError("short write")
                destination.flush()
            except Exception as exc:
                self._remember_error("cannot write raw script output", exc)
            else:
                active_destinations.append(destination)
        self._destinations = active_destinations
        return len(chunk)

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._source.close()
        finally:
            super().close()


class ProcessOutputCapture:
    """Drain one merged binary process pipe without blocking the child."""

    def __init__(
        self,
        stream: BinaryIO,
        *,
        live_text_streams: tuple[TextIO, ...] = (),
        raw_byte_streams: tuple[BinaryIO, ...] = (),
    ) -> None:
        self._buffer = _RollingLineBuffer()
        self._stream = stream
        self._live_text_streams = list(dict.fromkeys(live_text_streams))
        self._raw_byte_streams = tuple(dict.fromkeys(raw_byte_streams))
        self._error: tuple[str, Exception] | None = None
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
        """Return the last five lines for the bounded terminal view."""
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
        """Wait for EOF and report reader, decoding, or sink failures."""
        if not self._started:
            raise RuntimeError("script output capture has not started")
        if not self._finished:
            self._thread.join(timeout=timeout_seconds)
            if self._thread.is_alive():
                raise OSError("script output reader did not finish")
            self._finished = True
        if self._error is not None:
            context, error = self._error
            raise OSError(f"{context}: {error}")

    def _remember_error(self, context: str, error: Exception) -> None:
        if self._error is None:
            self._error = (context, error)

    def _publish_text(self, line: str) -> None:
        active_streams: list[TextIO] = []
        for destination in self._live_text_streams:
            try:
                destination.write(line)
                destination.flush()
            except Exception as exc:
                self._remember_error("cannot write script output", exc)
            else:
                active_streams.append(destination)
        self._live_text_streams = active_streams

    def _drain(self) -> None:
        text_stream: TextIOWrapper | None = None
        try:
            raw_tee = _RawOutputTee(
                self._stream,
                self._raw_byte_streams,
                self._remember_error,
            )
            text_stream = TextIOWrapper(
                BufferedReader(raw_tee),
                encoding="utf-8",
                errors="replace",
                newline=None,
            )
            for line in text_stream:
                self._buffer.append(line)
                self._publish_text(line)
        except Exception as exc:  # reported by finish() on the controlling thread
            self._remember_error("cannot read script output", exc)
        finally:
            try:
                if text_stream is None:
                    self._stream.close()
                else:
                    text_stream.close()
            except OSError as exc:
                self._remember_error("cannot close script output", exc)
