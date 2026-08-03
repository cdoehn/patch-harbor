"""Bounded capture, plain streaming, and temporary run logs."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import TextIOWrapper
import os
from pathlib import Path
from threading import Lock, Thread
import tempfile
from typing import BinaryIO, TextIO


RETAINED_OUTPUT_LINES = 10
VISIBLE_OUTPUT_LINES = 5
OUTPUT_READER_JOIN_SECONDS = 2.0


@dataclass(frozen=True)
class TemporaryRunLog:
    """One securely created persistent log in the system temp directory."""

    path: Path
    stream: TextIO


@contextmanager
def temporary_run_log() -> Iterator[TemporaryRunLog]:
    """Create a unique UTF-8 run log that remains after the command ends."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=".log",
        text=True,
    )
    path = Path(raw_path)
    stream: TextIO | None = None
    try:
        stream = os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        )
        yield TemporaryRunLog(path=path, stream=stream)
    except BaseException:
        if stream is None:
            try:
                os.close(descriptor)
            except OSError:
                pass
            path.unlink(missing_ok=True)
        raise
    finally:
        if stream is not None:
            stream.close()


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
    """Drain, decode, stream, and retain one merged binary process pipe."""

    def __init__(
        self,
        stream: BinaryIO,
        *,
        live_text_streams: tuple[TextIO, ...] = (),
    ) -> None:
        self._buffer = _RollingLineBuffer()
        self._stream = stream
        self._live_text_streams = list(dict.fromkeys(live_text_streams))
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

    def _publish(self, line: str) -> None:
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
            text_stream = TextIOWrapper(
                self._stream,
                encoding="utf-8",
                errors="replace",
                newline=None,
            )
            for line in text_stream:
                self._buffer.append(line)
                self._publish(line)
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
