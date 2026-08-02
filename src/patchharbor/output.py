"""Bounded and non-blocking capture of merged process output."""

from __future__ import annotations

import codecs
from collections import deque
from threading import Lock, Thread
from typing import BinaryIO


RETAINED_OUTPUT_LINES = 10
VISIBLE_OUTPUT_LINES = 5
OUTPUT_CHUNK_BYTES = 64 * 1024
OUTPUT_READER_JOIN_SECONDS = 2.0


class RollingLineBuffer:
    """Keep only the newest script-output lines and count evictions."""

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
        """Return the at most ten lines retained in memory."""
        with self._lock:
            return tuple(self._lines)

    @property
    def visible_lines(self) -> tuple[str, ...]:
        """Return the last five lines for the current simple output."""
        with self._lock:
            return tuple(self._lines)[-VISIBLE_OUTPUT_LINES:]

    @property
    def discarded_line_count(self) -> int:
        """Return how many older lines were evicted from the buffer."""
        with self._lock:
            return self._discarded_line_count


class _Utf8Decoder:
    """Decode arbitrary byte chunks incrementally and replace invalid input."""

    def __init__(self) -> None:
        decoder_type = codecs.getincrementaldecoder("utf-8")
        self._decoder = decoder_type(errors="replace")

    def feed(self, chunk: bytes) -> str:
        return self._decoder.decode(chunk, final=False)

    def finish(self) -> str:
        return self._decoder.decode(b"", final=True)


class _LineBuilder:
    """Turn decoded text chunks into normalized output lines."""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, text: str) -> tuple[str, ...]:
        self._pending += text
        return self._extract_lines(final=False)

    def finish(self, text: str = "") -> tuple[str, ...]:
        self._pending += text
        return self._extract_lines(final=True)

    def _extract_lines(self, *, final: bool) -> tuple[str, ...]:
        data = self._pending
        lines: list[str] = []
        start = 0
        index = 0

        while index < len(data):
            character = data[index]
            if character == "\n":
                lines.append(data[start:index] + "\n")
                start = index + 1
            elif character == "\r":
                if index + 1 == len(data) and not final:
                    break
                lines.append(data[start:index] + "\n")
                if index + 1 < len(data) and data[index + 1] == "\n":
                    index += 1
                start = index + 1
            index += 1

        self._pending = data[start:]
        if final and self._pending:
            lines.append(self._pending)
            self._pending = ""
        return tuple(lines)


class ProcessOutputCapture:
    """Drain one binary process pipe on a dedicated reader thread."""

    def __init__(
        self,
        stream: BinaryIO,
        *,
        chunk_size: int = OUTPUT_CHUNK_BYTES,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("output chunk size must be positive")
        self.buffer = RollingLineBuffer()
        self._stream = stream
        self._chunk_size = chunk_size
        self._errors: list[Exception] = []
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
        if self._errors:
            raise OSError(f"cannot read script output: {self._errors[0]}")

    def _drain(self) -> None:
        decoder = _Utf8Decoder()
        line_builder = _LineBuilder()
        try:
            while True:
                chunk = self._stream.read(self._chunk_size)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise TypeError("script output stream did not return bytes")
                for line in line_builder.feed(decoder.feed(chunk)):
                    self.buffer.append(line)

            for line in line_builder.finish(decoder.finish()):
                self.buffer.append(line)
        except Exception as exc:  # reported by finish() on the controlling thread
            self._errors.append(exc)
        finally:
            try:
                self._stream.close()
            except OSError as exc:
                self._errors.append(exc)
