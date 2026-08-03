"""Fixed terminal dashboard for one interactive PatchHarbor request."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import os
import shutil
from threading import Event, Lock, Thread
from typing import Callable, Protocol, TextIO


DASHBOARD_MAX_WIDTH = 80
DASHBOARD_REFRESH_SECONDS = 0.2
SOURCE_ROWS = 2
MESSAGE_ROWS = 4
FILE_ROWS = 3
EXECUTION_ROWS = 5
RESULT_ROWS = 2

_CLEAR_SCREEN = "\x1b[2J"
_CURSOR_HOME = "\x1b[H"
_CLEAR_TO_END = "\x1b[J"
_RESET = "\x1b[0m"
_CYAN = "\x1b[1;36m"
_BLUE = "\x1b[1;34m"
_GREEN = "\x1b[1;32m"
_YELLOW = "\x1b[1;33m"
_RED = "\x1b[1;31m"
_DIM = "\x1b[2m"


@dataclass(frozen=True, slots=True)
class PresentedFile:
    """One transferred file shown without exposing its content."""

    name: str
    size_bytes: int
    kind: str


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Immutable information required to render one dashboard frame."""

    source_name: str = "—"
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
    ) -> None:
        """Start the fixed dashboard for one validated request."""

    def begin_script(
        self,
        *,
        script_name: str,
        script_index: int,
        script_total: int,
        messages: tuple[tuple[str, str], ...],
        inline_files: tuple[PresentedFile, ...],
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
    ) -> None:
        """Stop periodic redraw and render the final state immediately."""


def _clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    text = text.replace("\t", "    ")
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def _fit(text: str, width: int) -> str:
    return _clip(text, width).ljust(max(0, width))


def _border(left: str, middle: str, right: str, width: int) -> str:
    if width <= 1:
        return left[:width]
    return left + middle * max(0, width - 2) + right


def _content(text: str, width: int) -> str:
    if width <= 1:
        return "│"[:width]
    return "│" + _fit(" " + text, width - 2) + "│"


def _section(title: str, width: int) -> str:
    if width <= 1:
        return "├"[:width]
    inner_width = width - 2
    label = f"─ {title} "
    label = _clip(label, inner_width)
    return "├" + label + "─" * max(0, inner_width - len(label)) + "┤"


def _message_rows(
    messages: tuple[tuple[str, str], ...],
    height: int,
) -> tuple[str, ...]:
    if not messages:
        return ("—",) + ("",) * (height - 1)

    rows: list[str] = []
    for message_index, (name, text) in enumerate(messages):
        content_lines = text.splitlines() or [""]
        block = [f"{name}: {content_lines[0]}"]
        block.extend(f"  {line}" for line in content_lines[1:])
        remaining = height - len(rows)
        if remaining <= 0:
            rows[-1] = (
                f"… +{len(messages) - message_index} weitere Messages"
            )
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
    lines = tuple(line.rstrip("\r\n") for line in snapshot.output_lines)
    if not lines:
        first = "waiting for script output…" if snapshot.status == "running" else "—"
        return (first,) + ("",) * (EXECUTION_ROWS - 1)
    rows = lines[-EXECUTION_ROWS:]
    return rows + ("",) * max(0, EXECUTION_ROWS - len(rows))


def _result_rows(snapshot: DashboardSnapshot) -> tuple[str, str]:
    if snapshot.status == "running":
        first = "status: running"
        second = (
            f"warnings: {len(snapshot.warnings)}"
            if snapshot.warnings
            else ""
        )
        return first, second
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

    if snapshot.log_path is not None:
        log_text = f"log: {snapshot.log_path}"
        second = f"{second} · {log_text}" if second else log_text
    return first, second


def _line_color(line: str, snapshot: DashboardSnapshot) -> str:
    if "PATCHHARBOR" in line:
        return _CYAN
    if any(label in line for label in ("SOURCE", "MESSAGES", "FILES", "EXECUTION")):
        return _BLUE
    if "RESULT" in line:
        if snapshot.status == "success":
            return _GREEN
        if snapshot.status in {"error", "failed"}:
            return _RED
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
        _content("PATCHHARBOR".center(max(0, width - 3)), width),
        _section("SOURCE", width),
        _content(f"source: {snapshot.source_name}", width),
        _content(f"script: {script_text}", width),
        _section("MESSAGES", width),
    ]
    rows.extend(_content(row, width) for row in _message_rows(snapshot.messages, MESSAGE_ROWS))
    rows.append(_section("FILES", width))
    rows.extend(_content(row, width) for row in _file_rows(snapshot.files, FILE_ROWS))
    execution_title = "EXECUTION"
    if snapshot.discarded_output_lines:
        execution_title += f" · +{snapshot.discarded_output_lines} older"
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


def _terminal_width(stream: TextIO) -> int:
    columns = shutil.get_terminal_size(
        fallback=(DASHBOARD_MAX_WIDTH, 24)
    ).columns
    try:
        terminal_size = os.get_terminal_size(stream.fileno())
        if terminal_size.columns > 0:
            columns = terminal_size.columns
    except (AttributeError, OSError):
        pass
    if columns <= 0:
        columns = DASHBOARD_MAX_WIDTH
    return max(4, min(DASHBOARD_MAX_WIDTH, columns))


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
        self._state_lock = Lock()
        self._write_lock = Lock()
        self._stop = Event()
        self._thread = Thread(
            target=self._redraw_loop,
            name="patchharbor-dashboard",
            daemon=True,
        )
        self._started = False
        self._first_frame = True
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
    ) -> None:
        with self._state_lock:
            self._bundle_files = bundle_files
            self._state = replace(
                self._state,
                source_name=source_name,
                script_total=script_total,
                files=bundle_files,
                status="preparing",
            )
            should_start = not self._started
            if should_start:
                self._started = True
        if should_start:
            self._render_now()
            self._thread.start()

    def begin_script(
        self,
        *,
        script_name: str,
        script_index: int,
        script_total: int,
        messages: tuple[tuple[str, str], ...],
        inline_files: tuple[PresentedFile, ...],
        warnings: tuple[str, ...],
    ) -> None:
        with self._state_lock:
            self._state = replace(
                self._state,
                script_name=script_name,
                script_index=script_index,
                script_total=script_total,
                messages=messages,
                files=self._bundle_files + inline_files,
                output_lines=(),
                discarded_output_lines=0,
                warnings=warnings,
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
    ) -> None:
        if not self._started:
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
            )
        self._stop.set()
        self._thread.join(timeout=max(1.0, self._refresh_seconds * 4))
        self._render_now()
        if self._render_error is not None:
            raise OSError(f"cannot render dashboard: {self._render_error}")

    def _snapshot(self) -> DashboardSnapshot:
        with self._state_lock:
            return self._state

    def _redraw_loop(self) -> None:
        while not self._stop.wait(self._refresh_seconds):
            self._render_now()
            if self._render_error is not None:
                self._stop.set()

    def _render_now(self) -> None:
        if self._render_error is not None:
            return
        snapshot = self._snapshot()
        try:
            width = self._width_supplier()
            frame = render_dashboard(
                snapshot,
                width=width,
                color_enabled=self._color_enabled,
            )
            with self._write_lock:
                prefix = _CLEAR_SCREEN + _CURSOR_HOME if self._first_frame else _CURSOR_HOME
                self._stream.write(prefix)
                self._stream.write(frame)
                self._stream.write(_CLEAR_TO_END)
                self._stream.flush()
                self._first_frame = False
        except Exception as exc:
            self._render_error = exc
