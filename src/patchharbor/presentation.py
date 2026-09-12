"""Colorful, append-only presentation; no frame, cursor movement or redraw loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from enum import Enum
import os
from threading import Event, RLock, Thread
from time import monotonic
from typing import TextIO
import unicodedata

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import DirectoryCandidate
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.progress import (
    ActivityEvent, PackageFile, ProgressEvent, RepositoryResolved,
    RequestStarted, ScriptPrepared,
)

_RESET = "\x1b[0m"
_COLORS = {
    "info": "\x1b[36m", "success": "\x1b[1;32m",
    "warning": "\x1b[1;33m", "error": "\x1b[1;31m",
    "heading": "\x1b[1;34m", "message": "\x1b[1;35m",
    "detail": "\x1b[2m",
}

# Per-file successes are still technical details. Severity alone must not turn
# hundreds of ZIP/Git/file operations into normal-mode records.
_DETAIL_PHASES = frozenset({
    "GIT", "ZIP", "RESULT-ZIP", "OPEN", "SHA256", "FILE", "WRITE", "TARGET",
    "MKDIR", "MANIFEST", "HANDOFF", "PREPARE", "IDENTIFY", "CACHE", "STATE",
    "RESERVE", "VERIFY", "SYNC", "RECEIPT", "LOCK", "PATCH", "MATCH", "REPLAY",
})
_COMPACT_RESULTS = frozenset({
    "SCAN", "ARCHIVE", "RECOVERY", "SNAPSHOT", "PUBLISH", "PAYLOAD", "SELECT",
    "BINDING", "RECHECK", "DRY-RUN", "PACKAGE", "SCRIPT", "EXEC", "RESULT",
    "BUNDLE", "SOURCE",
})
_WORK_LABELS = {
    "GIT": ("STATE", "Check repository state"),
    "ZIP": ("PACKAGE", "Inspect package contents"),
    "RESULT-ZIP": ("RESULT", "Write Result Bundle"),
    "WRITE": ("PAYLOAD", "Write payload files"),
    "TARGET": ("PAYLOAD", "Validate payload targets"),
    "OPEN": ("INPUT", "Read and identify input"),
}
_DOT_INTERVAL = 0.8


def _compact_visible(phase: str, level: str) -> bool:
    """One global policy for all human activity, never for script output."""
    if level in {"error", "warning", "message"}:
        return True
    if phase in _DETAIL_PHASES:
        return False
    return (
        level == "heading"
        or (level == "success" and phase in _COMPACT_RESULTS)
        or (phase in {"CONTEXT", "LOG"} and level != "detail")
    )


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

    def __init__(self, console: StreamingConsole, *, warning: bool = False,
                 selection: bool = False) -> None:
        self._console = console
        self._warning = warning
        self._selection = selection
        self._filter = _ChildTextFilter()

    def write(self, text: str) -> int:
        if self._selection:
            self._console.write_selection(self._filter.feed(text))
        elif self._warning:
            self._console.activity("WARN", text.rstrip("\n"), "warning")
        else:
            self._console.write_child(self._filter.feed(text))
        return len(text)

    def flush(self) -> None:
        self._console.flush()


class StreamingConsole:
    """Write complete chronological records and live child chunks to one stream."""

    def __init__(self, stream: TextIO, *, color_enabled: bool,
                 plain: bool = False, child_output: TextIO | None = None,
                 verbose: bool = False) -> None:
        self._stream = stream
        self._child_output = child_output
        self._color = (color_enabled and not plain and _stream_is_terminal(stream)
                       and "NO_COLOR" not in os.environ
                       and os.environ.get("TERM") != "dumb")
        self._plain = plain
        self._verbose = verbose
        self._progress_line_open = False
        self._executing = False
        self._last_dot = monotonic()
        self._stop = Event()
        self._heartbeat: Thread | None = None
        self._lock = RLock()
        self._started = False
        self._child_line_open = False
        self._closed = False
        self.child_stream = _ConsoleTextStream(self)
        self.selection_stream = _ConsoleTextStream(self, selection=True)
        self.warning_stream = _ConsoleTextStream(self, warning=True)
        if not verbose:
            self._heartbeat = Thread(
                target=self._pulse, name="patchharbor-console-progress", daemon=True,
            )
            self._heartbeat.start()

    def _pulse(self) -> None:
        # Waiting is presentation-only. It never reads a repository or Exchange
        # file and can neither grant permission nor delay a Core operation.
        while not self._stop.wait(_DOT_INTERVAL):
            with self._lock:
                now = monotonic()
                if (self._closed or not self._progress_line_open
                        or self._executing or now - self._last_dot < _DOT_INTERVAL):
                    continue
                try:
                    self._write(self._paint(".", "info"))
                    self._last_dot = monotonic()
                except Exception:
                    # Optional progress cannot kill a running patch. Required
                    # output/log writes retain their normal error handling.
                    self._stop.set()
                    return

    def _end_progress_line(self) -> None:
        if self._progress_line_open:
            self._write("\n")
            self._progress_line_open = False

    def _record(self, phase: str, message: str, level: str, *, ongoing: bool) -> None:
        self._end_progress_line()
        prefix = "\n" if self._child_line_open else ""
        self._child_line_open = False
        symbol = "" if self._plain else {
            "success": "✓ ", "warning": "! ", "error": "✗ ",
            "heading": "◆ ", "message": "◆ ",
        }.get(level, "› ")
        label = _sanitize_line(phase)
        stamp = datetime.now().strftime("%H:%M:%S")
        rendered = [
            self._paint(f"[{stamp}] {symbol}{label:<8} {line}", level)
            for line in _sanitize_lines(message)
        ]
        self._write(prefix + "\n".join(rendered) + (" " if ongoing else "\n"))
        self._progress_line_open = ongoing
        # Never catch up with a burst of dots after a stalled writer.
        self._last_dot = monotonic()

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
            if phase == "EXEC":
                # Child stdout/stderr is a separate, lossless stream. Do not
                # append heartbeat characters to prompts or script output.
                self._executing = True
            elif level == "heading" and phase not in {"SCRIPT", "MESSAGE"}:
                self._executing = False
            if not self._verbose and not _compact_visible(phase, level):
                if not self._progress_line_open and not self._executing:
                    label, text = _WORK_LABELS.get(phase, ("WORK", "Process request"))
                    self._record(label, text, "info", ongoing=True)
                return
            self._record(
                phase, message, level,
                ongoing=(not self._verbose and level == "heading"
                         and phase not in {"EXEC", "SCRIPT", "MESSAGE", "REPO"}),
            )

    def write_child(self, text: str) -> None:
        with self._lock:
            if self._closed or not text:
                return
            self._started = True
            self._executing = True
            self._end_progress_line()
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

    def write_selection(self, text: str) -> None:
        """Keep an interactive selection prompt clear of heartbeat characters."""
        with self._lock:
            if self._closed or not text:
                return
            self._executing = True
            self._end_progress_line()
            if self._child_output is not None:
                self._child_output.write(text)
                self._child_output.flush()
            else:
                self._write(text)
                self._child_line_open = not text.endswith("\n")

    def flush(self) -> None:
        with self._lock:
            self._stream.flush()

    def observe(self, event: ProgressEvent) -> None:
        """Adapt neutral Core facts to the selected human presentation."""
        if isinstance(event, ActivityEvent):
            message = event.message
            for identifier in event.identifiers:
                message = message.replace(identifier, shorten_identifier(identifier))
            self.activity(event.phase, message, event.level)
        elif isinstance(event, RequestStarted):
            self.begin_request(
                source_name=event.source_name, bundle_files=event.files,
                script_total=event.script_total, warnings=event.warnings,
            )
            if event.requested_repo_id is not None:
                self.activity("CONTEXT", f"repo_id: {shorten_identifier(event.requested_repo_id)}")
        elif isinstance(event, RepositoryResolved):
            context = event.context
            self.update_repository(
                repository_name=str(context.repository_path),
                repository_context=(
                    f"repo_id: {shorten_identifier(context.repo_id)} · "
                    f"base: {shorten_identifier(context.base_commit)} · "
                    f"state: {shorten_identifier(context.state_fingerprint)}"
                ),
            )
        elif isinstance(event, ScriptPrepared):
            self.begin_script(
                script_name=event.name, script_index=event.index,
                script_total=event.total, messages=event.messages,
                warnings=event.warnings,
            )

    def begin_request(self, *, source_name: str,
                      bundle_files: tuple[PackageFile, ...], script_total: int,
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
        self._stop.set()
        try:
            with self._lock:
                if self._closed:
                    return
                self._closed = True
                self._end_progress_line()
                if self._child_line_open:
                    self._write("\n")
                    self._child_line_open = False
        finally:
            if self._heartbeat is not None:
                # No output occurs after close returns; never join under the
                # writer lock, which the heartbeat may be about to acquire.
                self._heartbeat.join()


def select_directory_candidate(
    candidates: tuple[DirectoryCandidate, ...],
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> DirectoryCandidate:
    """Choose exactly one candidate without accessing the filesystem."""
    if len(candidates) == 1:
        return candidates[0]

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index} {candidate.display_name}", file=output_stream)

    count = len(candidates)
    while True:
        print(
            f"Select [1-{count}]: ",
            end="",
            file=output_stream,
            flush=True,
        )
        value = input_stream.readline().strip()
        if not value:
            raise PatchHarborError(
                "no script selected",
                ExitCode.USAGE_ERROR,
            )

        if value.isascii() and value.isdecimal():
            index = int(value) - 1
            if 0 <= index < count:
                return candidates[index]

        print(f"Enter 1-{count}.", file=output_stream)
