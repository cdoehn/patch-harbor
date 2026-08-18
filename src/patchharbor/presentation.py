"""Protected fixed terminal dashboard for one interactive PatchHarbor request."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import os
import shutil
from threading import Event, Lock, Thread, current_thread
from typing import Callable, Protocol, TextIO
import unicodedata


DASHBOARD_MAX_WIDTH = 80
DASHBOARD_MIN_WIDTH = 40
DASHBOARD_REFRESH_SECONDS = 0.2
SOURCE_ROWS = 2
MESSAGE_ROWS = 4
FILE_ROWS = 3
EXECUTION_ROWS = 5
RESULT_ROWS = 2

_CLEAR_SCREEN = "\x1b[2J"
_CURSOR_HOME = "\x1b[H"
_CLEAR_TO_END = "\x1b[J"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_RESET = "\x1b[0m"
_CYAN = "\x1b[1;36m"
_BLUE = "\x1b[1;34m"
_GREEN = "\x1b[1;32m"
_YELLOW = "\x1b[1;33m"
_RED = "\x1b[1;31m"
_DIM = "\x1b[2m"
_DASHBOARD_GLYPHS = "┌─┐│├┤└┘…"


@dataclass(frozen=True, slots=True)
class PresentedFile:
    """One transferred file shown without exposing its content."""

    name: str
    size_bytes: int
    kind: str


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Immutable presentation-only information for one dashboard frame."""

    source_name: str = "—"
    repository_name: str | None = None
    repository_context: str | None = None
    script_name: str = "—"
    script_index: int = 0
    script_total: int = 0
    messages: tuple[tuple[str, str], ...] = ()
    files: tuple[PresentedFile, ...] = ()
    output_lines: tuple[str, ...] = ()
    discarded_output_lines: int = 0
    warnings: tuple[str, ...] = ()
    status: str = "preparing"
    exit_code: int | None = None
    tool_error: str | None = None
    log_path: str | None = None
    result_path: str | None = None


class DashboardPresentation(Protocol):
    """Small application-facing contract for interactive presentation."""

    @property
    def started(self) -> bool:
        """Return whether the dashboard has drawn its first frame."""

    def begin_request(
        self,
        *,
        source_name: str,
        bundle_files: tuple[PresentedFile, ...],
        script_total: int,
        warnings: tuple[str, ...] = (),
        repository_name: str | None = None,
        repository_context: str | None = None,
    ) -> None:
        """Start the fixed dashboard for one validated request."""

    def update_repository(
        self,
        *,
        repository_name: str,
        repository_context: str | None,
    ) -> None:
        """Show the safely resolved repository and its checked context."""

    def begin_script(
        self,
        *,
        script_name: str,
        script_index: int,
        script_total: int,
        messages: tuple[tuple[str, str], ...],
        warnings: tuple[str, ...],
    ) -> None:
        """Show context for the next script in the bundle."""

    def update_output(
        self,
        lines: tuple[str, ...],
        discarded_line_count: int,
    ) -> None:
        """Update the bounded execution output without rendering immediately."""

    def finish(
        self,
        *,
        exit_code: int,
        tool_error: str | None,
        log_path: Path | None,
        result_path: Path | None = None,
    ) -> None:
        """Stop periodic redraw, render the final state, and restore the terminal."""

    def close(self) -> None:
        """Restore terminal state without masking an active application error."""


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


def _character_width(character: str) -> int:
    if unicodedata.combining(character):
        return 0
    if unicodedata.category(character) in {"Mn", "Me", "Cf"}:
        return 0
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def _display_width(text: str) -> int:
    return sum(_character_width(character) for character in text)


def _clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    safe_text = _sanitize_line(text)
    if _display_width(safe_text) <= width:
        return safe_text
    if width == 1:
        return "…"

    target_width = width - 1
    current_width = 0
    result: list[str] = []
    for character in safe_text:
        character_width = _character_width(character)
        if character_width and current_width + character_width > target_width:
            break
        result.append(character)
        current_width += character_width
    return "".join(result) + "…"


def _fit(text: str, width: int) -> str:
    clipped = _clip(text, width)
    return clipped + " " * max(0, width - _display_width(clipped))


def _center(text: str, width: int) -> str:
    clipped = _clip(text, width)
    remaining = max(0, width - _display_width(clipped))
    left = remaining // 2
    return " " * left + clipped + " " * (remaining - left)


def _border(left: str, middle: str, right: str, width: int) -> str:
    if width <= 1:
        return left[:width]
    return left + middle * max(0, width - 2) + right


def _content(text: str, width: int) -> str:
    if width <= 1:
        return "│"[:width]
    return "│" + _fit(" " + text, width - 2) + "│"


def _centered_content(text: str, width: int) -> str:
    if width <= 1:
        return "│"[:width]
    return "│" + _center(text, width - 2) + "│"


def _section(title: str, width: int) -> str:
    if width <= 1:
        return "├"[:width]
    inner_width = width - 2
    label = _clip(f"─ {title} ", inner_width)
    return "├" + label + "─" * max(0, inner_width - _display_width(label)) + "┤"


def _message_rows(
    messages: tuple[tuple[str, str], ...],
    height: int,
) -> tuple[str, ...]:
    if not messages:
        return ("—",) + ("",) * (height - 1)

    rows: list[str] = []
    for message_index, (name, text) in enumerate(messages):
        content_lines = _sanitize_lines(text) or ("",)
        block = [f"{_sanitize_line(name)}: {content_lines[0]}"]
        block.extend(f"  {line}" for line in content_lines[1:])
        remaining = height - len(rows)
        if remaining <= 0:
            rows[-1] = f"… +{len(messages) - message_index} weitere Messages"
            break
        if len(block) <= remaining:
            rows.extend(block)
            continue

        if remaining > 1:
            rows.extend(block[: remaining - 1])
        hidden_messages = len(messages) - message_index - 1
        if hidden_messages:
            rows.append(f"… +{hidden_messages} weitere Messages")
        else:
            rows.append("… Message gekürzt")
        break

    return tuple(rows[:height]) + ("",) * max(0, height - len(rows))


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    return f"{size_bytes / (1024 * 1024):.1f} MiB"


def _file_rows(
    files: tuple[PresentedFile, ...],
    height: int,
) -> tuple[str, ...]:
    if not files:
        return ("—",) + ("",) * (height - 1)

    if len(files) <= height:
        rows = [
            f"{item.kind}: {item.name} ({_format_size(item.size_bytes)})"
            for item in files
        ]
    else:
        visible = files[: max(0, height - 1)]
        rows = [
            f"{item.kind}: {item.name} ({_format_size(item.size_bytes)})"
            for item in visible
        ]
        rows.append(f"… +{len(files) - len(visible)} weitere Dateien")
    return tuple(rows[:height]) + ("",) * max(0, height - len(rows))


def _execution_rows(snapshot: DashboardSnapshot) -> tuple[str, ...]:
    lines = tuple(_sanitize_line(line.rstrip("\r\n")) for line in snapshot.output_lines)
    if not lines:
        first = "waiting for script output…" if snapshot.status == "running" else "—"
        return (first,) + ("",) * (EXECUTION_ROWS - 1)
    rows = lines[-EXECUTION_ROWS:]
    return rows + ("",) * max(0, EXECUTION_ROWS - len(rows))


def _warning_summary(warnings: tuple[str, ...]) -> str:
    if not warnings:
        return ""
    first = _sanitize_line(warnings[0])
    suffix = f" · +{len(warnings) - 1}" if len(warnings) > 1 else ""
    return f"warning: {first}{suffix}"


def _result_rows(snapshot: DashboardSnapshot) -> tuple[str, str]:
    if snapshot.status == "running":
        return "status: running", _warning_summary(snapshot.warnings)
    if snapshot.status == "preparing":
        return "status: preparing", ""

    if snapshot.tool_error is not None:
        first = f"status: error · exit code: {snapshot.exit_code}"
        second = f"detail: {snapshot.tool_error}"
    elif snapshot.exit_code == 0:
        first = "status: success · exit code: 0"
        second = ""
    else:
        first = f"status: failed · exit code: {snapshot.exit_code}"
        second = ""

    if not second:
        second = _warning_summary(snapshot.warnings)
    if snapshot.log_path is not None:
        log_text = f"log: {snapshot.log_path}"
        second = f"{second} · {log_text}" if second else log_text
    if snapshot.result_path is not None:
        result_text = f"result: {snapshot.result_path}"
        second = f"{second} · {result_text}" if second else result_text
    return first, second


def _line_color(line: str, snapshot: DashboardSnapshot) -> str:
    if "PATCHHARBOR" in line:
        return _CYAN
    if any(
        label in line
        for label in ("SOURCE", "REPOSITORY", "MESSAGES", "FILES", "EXECUTION")
    ):
        return _BLUE
    if "RESULT" in line:
        if snapshot.status == "success":
            return _GREEN
        if snapshot.status in {"error", "failed"}:
            return _RED
        return _YELLOW
    if "warning:" in line:
        return _YELLOW
    if "weitere" in line or "gekürzt" in line:
        return _DIM
    if "status: success" in line:
        return _GREEN
    if "status: error" in line or "status: failed" in line:
        return _RED
    if "status: running" in line or "status: preparing" in line:
        return _YELLOW
    return ""


def render_dashboard(
    snapshot: DashboardSnapshot,
    *,
    width: int,
    color_enabled: bool = False,
) -> str:
    """Render one complete fixed-height dashboard frame."""
    width = max(4, min(DASHBOARD_MAX_WIDTH, width))
    script_text = "—"
    if snapshot.script_total:
        script_text = (
            f"{snapshot.script_name} "
            f"({snapshot.script_index}/{snapshot.script_total})"
        )

    rows: list[str] = [
        _border("┌", "─", "┐", width),
        _centered_content("PATCHHARBOR", width),
        _section("SOURCE", width),
        _content(f"source: {snapshot.source_name}", width),
        _content(f"script: {script_text}", width),
    ]
    if snapshot.repository_name is not None:
        rows.append(_section("REPOSITORY", width))
        rows.extend(
            (
                _content(f"repository: {snapshot.repository_name}", width),
                _content(snapshot.repository_context or "—", width),
            )
        )
    rows.append(_section("MESSAGES", width))
    rows.extend(_content(row, width) for row in _message_rows(snapshot.messages, MESSAGE_ROWS))
    rows.append(_section("FILES", width))
    rows.extend(_content(row, width) for row in _file_rows(snapshot.files, FILE_ROWS))
    execution_title = "EXECUTION"
    if snapshot.discarded_output_lines:
        execution_title += f" · +{snapshot.discarded_output_lines} weitere Zeilen"
    rows.append(_section(execution_title, width))
    rows.extend(_content(row, width) for row in _execution_rows(snapshot))
    rows.append(_section("RESULT", width))
    rows.extend(_content(row, width) for row in _result_rows(snapshot))
    rows.append(_border("└", "─", "┘", width))

    if color_enabled:
        rows = [
            f"{color}{line}{_RESET}" if (color := _line_color(line, snapshot)) else line
            for line in rows
        ]
    return "\n".join(rows) + "\n"


def _stream_is_terminal(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except (AttributeError, OSError):
        return False


def _terminal_columns(stream: TextIO) -> int:
    columns = shutil.get_terminal_size(fallback=(DASHBOARD_MAX_WIDTH, 24)).columns
    try:
        terminal_size = os.get_terminal_size(stream.fileno())
        if terminal_size.columns > 0:
            columns = terminal_size.columns
    except (AttributeError, OSError):
        pass
    return columns


def _stream_supports_dashboard_glyphs(stream: TextIO) -> bool:
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return True
    try:
        _DASHBOARD_GLYPHS.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def terminal_supports_dashboard(stream: TextIO) -> bool:
    """Return whether a fixed Unicode dashboard is safe for this stream."""
    return (
        _stream_is_terminal(stream)
        and _terminal_columns(stream) >= DASHBOARD_MIN_WIDTH
        and _stream_supports_dashboard_glyphs(stream)
    )


def _terminal_width(stream: TextIO) -> int:
    return max(4, min(DASHBOARD_MAX_WIDTH, _terminal_columns(stream)))


class TerminalDashboard:
    """Periodically redraw one fixed dashboard while a script is running."""

    def __init__(
        self,
        stream: TextIO,
        *,
        color_enabled: bool,
        refresh_seconds: float = DASHBOARD_REFRESH_SECONDS,
        width_supplier: Callable[[], int] | None = None,
    ) -> None:
        self._stream = stream
        self._color_enabled = color_enabled
        self._refresh_seconds = refresh_seconds
        self._width_supplier = width_supplier or (lambda: _terminal_width(stream))
        self._state = DashboardSnapshot()
        self._bundle_files: tuple[PresentedFile, ...] = ()
        self._request_warnings: tuple[str, ...] = ()
        self._state_lock = Lock()
        self._write_lock = Lock()
        self._stop = Event()
        self._thread = Thread(
            target=self._redraw_loop,
            name="patchharbor-dashboard",
            daemon=True,
        )
        self._started = False
        self._thread_started = False
        self._last_frame: str | None = None
        self._cursor_hidden = False
        self._closed = False
        self._render_error: Exception | None = None

    @property
    def started(self) -> bool:
        return self._started

    def begin_request(
        self,
        *,
        source_name: str,
        bundle_files: tuple[PresentedFile, ...],
        script_total: int,
        warnings: tuple[str, ...] = (),
        repository_name: str | None = None,
        repository_context: str | None = None,
    ) -> None:
        with self._state_lock:
            self._bundle_files = bundle_files
            self._request_warnings = warnings
            self._state = replace(
                self._state,
                source_name=source_name,
                repository_name=repository_name,
                repository_context=repository_context,
                script_total=script_total,
                files=bundle_files,
                warnings=warnings,
                status="preparing",
            )
            should_start = not self._started
            if should_start:
                self._started = True
        if should_start:
            self._render_now()
            if self._render_error is not None:
                error = self._render_error
                self.close()
                raise OSError(f"cannot render dashboard: {error}")
            self._thread.start()
            self._thread_started = True

    def update_repository(
        self,
        *,
        repository_name: str,
        repository_context: str | None,
    ) -> None:
        with self._state_lock:
            self._state = replace(
                self._state,
                repository_name=repository_name,
                repository_context=repository_context,
            )

    def begin_script(
        self,
        *,
        script_name: str,
        script_index: int,
        script_total: int,
        messages: tuple[tuple[str, str], ...],
        warnings: tuple[str, ...],
    ) -> None:
        with self._state_lock:
            self._state = replace(
                self._state,
                script_name=script_name,
                script_index=script_index,
                script_total=script_total,
                messages=messages,
                files=self._bundle_files,
                output_lines=(),
                discarded_output_lines=0,
                warnings=self._request_warnings + warnings,
                status="running",
                exit_code=None,
                tool_error=None,
            )

    def update_output(
        self,
        lines: tuple[str, ...],
        discarded_line_count: int,
    ) -> None:
        with self._state_lock:
            self._state = replace(
                self._state,
                output_lines=lines,
                discarded_output_lines=discarded_line_count,
            )

    def finish(
        self,
        *,
        exit_code: int,
        tool_error: str | None,
        log_path: Path | None,
        result_path: Path | None = None,
    ) -> None:
        if not self._started or self._closed:
            return
        status = "error" if tool_error is not None else (
            "success" if exit_code == 0 else "failed"
        )
        with self._state_lock:
            self._state = replace(
                self._state,
                status=status,
                exit_code=exit_code,
                tool_error=tool_error,
                log_path=None if log_path is None else str(log_path),
                result_path=None if result_path is None else str(result_path),
            )
        self._stop_loop()
        self._render_now(force=True)
        render_error = self._render_error
        self.close()
        if render_error is not None:
            raise OSError(f"cannot render dashboard: {render_error}")

    def close(self) -> None:
        """Stop redraw and restore terminal controls; safe to call repeatedly."""
        if self._closed:
            return
        self._stop_loop()
        if self._cursor_hidden:
            try:
                with self._write_lock:
                    self._stream.write(_RESET + _SHOW_CURSOR)
                    self._stream.flush()
            except Exception as exc:
                if self._render_error is None:
                    self._render_error = exc
            self._cursor_hidden = False
        self._closed = True

    def _stop_loop(self) -> None:
        self._stop.set()
        if (
            self._thread_started
            and self._thread.is_alive()
            and current_thread() is not self._thread
        ):
            self._thread.join(timeout=max(1.0, self._refresh_seconds * 4))

    def _snapshot(self) -> DashboardSnapshot:
        with self._state_lock:
            return self._state

    def _redraw_loop(self) -> None:
        while not self._stop.wait(self._refresh_seconds):
            self._render_now()
            if self._render_error is not None:
                self._stop.set()

    def _render_now(self, *, force: bool = False) -> None:
        if self._render_error is not None or self._closed:
            return
        snapshot = self._snapshot()
        try:
            width = self._width_supplier()
            frame = render_dashboard(
                snapshot,
                width=width,
                color_enabled=self._color_enabled,
            )
            if not force and frame == self._last_frame:
                return

            first_frame = self._last_frame is None
            if first_frame:
                self._cursor_hidden = True
                prefix = _HIDE_CURSOR + _RESET + _CLEAR_SCREEN + _CURSOR_HOME
            else:
                prefix = _RESET + _CURSOR_HOME
            with self._write_lock:
                self._stream.write(prefix + frame + _RESET + _CLEAR_TO_END)
                self._stream.flush()
            self._last_frame = frame
        except Exception as exc:
            self._render_error = exc
