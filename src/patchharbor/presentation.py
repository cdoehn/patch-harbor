"""Colorful, append-only presentation; no frame, cursor movement or redraw loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from enum import Enum
import os
from threading import RLock
from typing import Protocol, TextIO
import unicodedata

_RESET = "\x1b[0m"
_COLORS = {
    "info": "\x1b[36m", "success": "\x1b[1;32m",
    "warning": "\x1b[1;33m", "error": "\x1b[1;31m",
    "heading": "\x1b[1;34m", "message": "\x1b[1;35m",
    "detail": "\x1b[2m",
}

class PresentedStatus(str, Enum):
    """Presentation-only completion state chosen by the application boundary."""

    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PresentedCompletion:
    """Fully decided completion data rendered without business decisions."""

    status: PresentedStatus
    exit_code: int
    detail: str | None = None
    log_path: Path | None = None
    result_path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, PresentedStatus):
            raise ValueError("presented status must be a PresentedStatus")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("presented exit code must be an integer")
        if self.status is PresentedStatus.SUCCESS and self.exit_code != 0:
            raise ValueError("presented success requires exit code zero")
        if self.status is not PresentedStatus.SUCCESS and self.exit_code == 0:
            raise ValueError("presented failure requires a nonzero exit code")
        if self.status is PresentedStatus.ERROR and self.detail is None:
            raise ValueError("presented error requires a detail")
        if self.status is not PresentedStatus.ERROR and self.detail is not None:
            raise ValueError("only a presented error may carry a detail")


@dataclass(frozen=True, slots=True)
class PresentedFile:
    """One transferred file shown without exposing its content."""

    name: str
    size_bytes: int
    kind: str


class ConsolePresentation(Protocol):
    """Presentation only: the application supplies already-decided facts."""

    @property
    def started(self) -> bool: ...

    def begin_request(self, *, source_name: str,
                      bundle_files: tuple[PresentedFile, ...], script_total: int,
                      warnings: tuple[str, ...] = (),
                      repository_name: str | None = None,
                      repository_context: str | None = None) -> None: ...

    def update_repository(self, *, repository_name: str,
                          repository_context: str | None) -> None: ...

    def begin_script(self, *, script_name: str, script_index: int,
                     script_total: int, messages: tuple[tuple[str, str], ...],
                     warnings: tuple[str, ...]) -> None: ...

    def finish(self, completion: PresentedCompletion) -> None: ...

    def close(self) -> None: ...


def _skip_control_string(text: str, index: int) -> int:
    """Skip an OSC/DCS-like control string ending in BEL or ST."""
    while index < len(text):
        if text[index] == "\x07":
            return index + 1
        if (
            text[index] == "\x1b"
            and index + 1 < len(text)
            and text[index + 1] == "\\"
        ):
            return index + 2
        index += 1
    return index


def _strip_terminal_sequences(text: str) -> str:
    """Remove ANSI/ECMA-48 escape sequences from untrusted visible text."""
    result: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character != "\x1b":
            result.append(character)
            index += 1
            continue

        index += 1
        if index >= len(text):
            break
        introducer = text[index]
        index += 1

        if introducer == "[":
            while index < len(text):
                value = ord(text[index])
                index += 1
                if 0x40 <= value <= 0x7E:
                    break
            continue
        if introducer in "]PX^_":
            index = _skip_control_string(text, index)
            continue
        # A two-character escape sequence is fully consumed here.
    return "".join(result)


def _sanitize_line(text: str) -> str:
    """Return one harmless terminal line without embedded control effects."""
    stripped = _strip_terminal_sequences(text)
    result: list[str] = []
    for character in stripped:
        if character == "\t":
            result.append("    ")
            continue
        if character in "\r\n":
            result.append(" ")
            continue
        category = unicodedata.category(character)
        if category in {"Cc", "Cf", "Cs"}:
            continue
        result.append(character)
    return "".join(result)


def _sanitize_lines(text: str) -> tuple[str, ...]:
    """Preserve intentional message line boundaries while removing controls."""
    stripped = _strip_terminal_sequences(text)
    normalized = stripped.replace("\r\n", "\n").replace("\r", "\n")
    return tuple(_sanitize_line(line) for line in normalized.split("\n"))


def sanitize_visible_text(text: str) -> str:
    """Remove terminal effects while preserving ordinary visible line breaks."""
    stripped = _strip_terminal_sequences(text)
    result: list[str] = []
    for character in stripped:
        if character == "\n":
            result.append(character)
            continue
        if character == "\t":
            result.append("    ")
            continue
        if character == "\r":
            continue
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            continue
        result.append(character)
    return "".join(result)


class SanitizedTextStream:
    """Small text sink that protects a visible terminal from child output."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    @property
    def encoding(self) -> str | None:
        return getattr(self._stream, "encoding", None)

    def isatty(self) -> bool:
        return _stream_is_terminal(self._stream)

    def write(self, text: str) -> int:
        self._stream.write(sanitize_visible_text(text))
        return len(text)

    def flush(self) -> None:
        self._stream.flush()


def _stream_is_terminal(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except (AttributeError, OSError):
        return False


class _ChildTextFilter:
    """Discard child terminal commands, including sequences split across reads."""

    def __init__(self) -> None:
        self._state = "text"

    def feed(self, text: str) -> str:
        visible: list[str] = []
        for char in text:
            state = self._state
            if state == "escape":
                if char == "[":
                    self._state = "csi"
                elif char in "]PX^_":
                    self._state = "string"
                else:
                    self._state = "text"
                continue
            if state == "csi":
                if 0x40 <= ord(char) <= 0x7e:
                    self._state = "text"
                continue
            if state == "string":
                if char in ("\x07", "\x9c"):
                    self._state = "text"
                elif char == "\x1b":
                    self._state = "string_escape"
                continue
            if state == "string_escape":
                self._state = "text" if char == "\\" else "string"
                continue
            if char == "\x1b":
                self._state = "escape"
            elif char == "\x9b":
                self._state = "csi"
            elif char in "\x90\x98\x9d\x9e\x9f":
                self._state = "string"
            elif char in "\r\n":
                visible.append("\n")
            elif char == "\t":
                visible.append("    ")
            elif unicodedata.category(char) not in {"Cc", "Cf", "Cs"}:
                visible.append(char)
        return "".join(visible)


class _ConsoleTextStream:
    """A sink for either incremental child text or complete warning messages."""

    def __init__(self, console: StreamingConsole, *, warning: bool = False) -> None:
        self._console = console
        self._warning = warning
        self._filter = _ChildTextFilter()

    def write(self, text: str) -> int:
        if self._warning:
            self._console.activity("WARN", text.rstrip("\n"), "warning")
        else:
            self._console.write_child(self._filter.feed(text))
        return len(text)

    def flush(self) -> None:
        self._console.flush()


class StreamingConsole:
    """Write complete chronological records and live child chunks to one stream."""

    def __init__(self, stream: TextIO, *, color_enabled: bool,
                 plain: bool = False, child_output: TextIO | None = None) -> None:
        self._stream = stream
        self._child_output = child_output
        self._color = (color_enabled and not plain and _stream_is_terminal(stream)
                       and "NO_COLOR" not in os.environ
                       and os.environ.get("TERM") != "dumb")
        self._plain = plain
        self._lock = RLock()
        self._started = False
        self._child_line_open = False
        self._closed = False
        self.child_stream = _ConsoleTextStream(self)
        self.warning_stream = _ConsoleTextStream(self, warning=True)

    @property
    def started(self) -> bool:
        return self._started

    @property
    def separate_child_output(self) -> bool:
        return self._child_output is not None

    def _write(self, text: str) -> None:
        # Embedded callers may supply a legacy-codepage stream. Never lose the
        # actual path; only unrepresentable display glyphs get a safe fallback.
        encoding = getattr(self._stream, "encoding", None)
        if encoding:
            text = text.encode(encoding, errors="backslashreplace").decode(encoding)
        self._stream.write(text)
        self._stream.flush()

    def _paint(self, text: str, level: str) -> str:
        if self._color:
            return _COLORS.get(level, _COLORS["info"]) + text + _RESET
        return text

    def activity(self, phase: str, message: str, level: str = "info") -> None:
        with self._lock:
            if self._closed:
                return
            self._started = True
            prefix = "\n" if self._child_line_open else ""
            self._child_line_open = False
            symbol = "" if self._plain else {
                "success": "✓ ", "warning": "! ", "error": "✗ ",
                "heading": "◆ ", "message": "◆ ",
            }.get(level, "› ")
            label = _sanitize_line(phase)
            stamp = datetime.now().strftime("%H:%M:%S")
            lines = _sanitize_lines(message)
            rendered = []
            for line in lines:
                text = f"[{stamp}] {symbol}{label:<8} {line}"
                rendered.append(self._paint(text, level))
            self._write(prefix + "\n".join(rendered) + "\n")

    def write_child(self, text: str) -> None:
        with self._lock:
            if self._closed or not text:
                return
            self._started = True
            if self._child_output is not None:
                self._child_output.write(text)
                self._child_output.flush()
                return
            parts: list[str] = []
            for part in text.splitlines(keepends=True):
                if not self._child_line_open:
                    stamp = datetime.now().strftime("%H:%M:%S")
                    parts.append(self._paint(f"[{stamp}] EXEC     ", "detail"))
                parts.append(part)
                self._child_line_open = not part.endswith("\n")
            self._write("".join(parts))

    def flush(self) -> None:
        with self._lock:
            self._stream.flush()

    def begin_request(self, *, source_name: str,
                      bundle_files: tuple[PresentedFile, ...], script_total: int,
                      warnings: tuple[str, ...] = (),
                      repository_name: str | None = None,
                      repository_context: str | None = None) -> None:
        self.activity("PACKAGE", source_name, "heading")
        self.activity("PACKAGE", f"Validated: {script_total} script(s), "
                      f"{len(bundle_files)} package file(s)", "success")
        for item in bundle_files:
            self.activity("FILE", f"{item.kind}: {item.name} ({item.size_bytes} bytes)")
        if repository_name is not None:
            self.update_repository(repository_name=repository_name,
                                   repository_context=repository_context)
        # Warnings are routed once through OutputTargets.warning_text_stream.

    def update_repository(self, *, repository_name: str,
                          repository_context: str | None) -> None:
        self.activity("REPO", repository_name, "heading")
        if repository_context:
            self.activity("CONTEXT", repository_context)

    def begin_script(self, *, script_name: str, script_index: int,
                     script_total: int, messages: tuple[tuple[str, str], ...],
                     warnings: tuple[str, ...]) -> None:
        self.activity("SCRIPT", f"Prepared {script_index}/{script_total}: {script_name}",
                      "heading")
        for name, text in messages:
            self.activity("MESSAGE", name, "message")
            self.activity("MESSAGE", text, "message")

    def finish(self, completion: PresentedCompletion) -> None:
        level = "success" if completion.status is PresentedStatus.SUCCESS else "error"
        self.activity("RESULT", f"{completion.status.value.upper()} "
                      f"(exit {completion.exit_code})", level)
        if completion.detail:
            self.activity("ERROR", completion.detail, "error")
        if completion.log_path is not None:
            self.activity("LOG", str(completion.log_path))
        if completion.result_path is not None:
            self.activity("BUNDLE", str(completion.result_path), "success")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._child_line_open:
                self._write("\n")
                self._child_line_open = False
