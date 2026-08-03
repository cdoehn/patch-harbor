from __future__ import annotations

from io import StringIO
from pathlib import Path
import time
import unicodedata

from patchharbor.application import run_script_path
from patchharbor.output import OutputTargets
from patchharbor.presentation import (
    DASHBOARD_MIN_WIDTH,
    DashboardSnapshot,
    PresentedFile,
    TerminalDashboard,
    render_dashboard,
    terminal_supports_dashboard,
)


class _RecordingPresentation:
    def __init__(self) -> None:
        self.started = False
        self.request: dict[str, object] | None = None
        self.script: dict[str, object] | None = None

    def begin_request(self, **values: object) -> None:
        self.started = True
        self.request = values

    def begin_script(self, **values: object) -> None:
        self.script = values

    def update_output(
        self,
        lines: tuple[str, ...],
        discarded_line_count: int,
    ) -> None:
        return None

    def finish(
        self,
        *,
        exit_code: int,
        tool_error: str | None,
        log_path: Path | None,
    ) -> None:
        return None

    def close(self) -> None:
        return None


class _EncodedTerminal(StringIO):
    def __init__(self, *, encoding: str) -> None:
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def isatty(self) -> bool:
        return True


class _CountingTerminal(_EncodedTerminal):
    def __init__(self, *, encoding: str = "utf-8") -> None:
        super().__init__(encoding=encoding)
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def _wait_until(predicate, *, timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("timed out waiting for dashboard update")


def _cell_width(text: str) -> int:
    width = 0
    for character in text:
        if unicodedata.combining(character):
            continue
        if unicodedata.category(character) in {"Mn", "Me", "Cf"}:
            continue
        width += 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
    return width


def test_dashboard_renderer_has_fixed_sections_width_and_overflow_hints() -> None:
    snapshot = DashboardSnapshot(
        source_name="downloads/patch-bundle.zip",
        script_name="scripts/apply-fix.sh",
        script_index=2,
        script_total=3,
        messages=tuple(
            (f"message.{index}", f"text {index}")
            for index in range(1, 7)
        ),
        files=tuple(
            PresentedFile(
                name=f"assets/file-{index}.bin",
                size_bytes=index * 2048,
                kind="bundle",
            )
            for index in range(1, 6)
        ),
        output_lines=tuple(f"line-{index}\n" for index in range(1, 6)),
        discarded_output_lines=12,
        status="running",
    )

    frame = render_dashboard(snapshot, width=60)
    lines = frame.splitlines()

    assert len(lines) == 24
    assert all(_cell_width(line) == 60 for line in lines)
    for section in ("SOURCE", "MESSAGES", "FILES", "EXECUTION", "RESULT"):
        assert section in frame
    assert "weitere Messages" in frame
    assert "weitere Dateien" in frame
    assert "weitere Zeilen" in frame
    assert "line-5" in frame
    assert "status: running" in frame


def test_dashboard_renderer_uses_actual_width_below_eighty() -> None:
    frame = render_dashboard(
        DashboardSnapshot(source_name="source", status="success", exit_code=0),
        width=47,
    )

    assert all(_cell_width(line) == 47 for line in frame.splitlines())
    assert "status: success" in frame


def test_dashboard_strips_terminal_controls_from_all_untrusted_visible_text() -> None:
    snapshot = DashboardSnapshot(
        source_name="\x1b]0;owned\x07source\x1b[2J",
        script_name="apply\x1b[31m-red\x1b[0m.sh",
        script_index=1,
        script_total=1,
        messages=(("message\x08", "hello\x1b[Hworld"),),
        files=(PresentedFile("asset\x1b[2J.bin", 3, "bundle"),),
        output_lines=("before\x1b[2J\x1b[31mafter\x1b[0m\n",),
        status="error",
        exit_code=7,
        tool_error="bad\x1b[Hdetail",
    )

    frame = render_dashboard(snapshot, width=60)

    assert "\x1b" not in frame
    assert "owned" not in frame
    assert "source" in frame
    assert "apply-red.sh" in frame
    assert "helloworld" in frame
    assert "beforeafter" in frame
    assert "baddetail" in frame


def test_dashboard_clips_wide_unicode_by_terminal_cells_without_wrapping() -> None:
    snapshot = DashboardSnapshot(
        source_name="界" * 80,
        script_name="patch-😀" * 20,
        script_index=1,
        script_total=1,
        output_lines=("🙂" * 80,),
        status="running",
    )

    frame = render_dashboard(snapshot, width=41)

    assert all(_cell_width(line) == 41 for line in frame.splitlines())
    assert "…" in frame


def test_dashboard_shows_first_warning_and_counts_the_rest_safely() -> None:
    snapshot = DashboardSnapshot(
        source_name="source",
        warnings=(
            "large input\x1b[2J",
            "second warning",
            "third warning",
        ),
        status="success",
        exit_code=0,
    )

    frame = render_dashboard(snapshot, width=60)

    assert "warning: large input · +2" in frame
    assert "\x1b" not in frame


def test_terminal_capability_rejects_narrow_or_non_unicode_terminals(
    monkeypatch,
) -> None:
    terminal = _EncodedTerminal(encoding="utf-8")
    monkeypatch.setattr(
        "patchharbor.presentation._terminal_columns",
        lambda stream: DASHBOARD_MIN_WIDTH - 1,
    )
    assert not terminal_supports_dashboard(terminal)

    monkeypatch.setattr(
        "patchharbor.presentation._terminal_columns",
        lambda stream: DASHBOARD_MIN_WIDTH,
    )
    assert not terminal_supports_dashboard(_EncodedTerminal(encoding="ascii"))
    assert terminal_supports_dashboard(terminal)


def test_dashboard_restores_cursor_and_color_after_final_frame() -> None:
    stream = _EncodedTerminal(encoding="utf-8")
    dashboard = TerminalDashboard(
        stream,
        color_enabled=True,
        refresh_seconds=10,
        width_supplier=lambda: 60,
    )

    dashboard.begin_request(
        source_name="script.sh",
        bundle_files=(),
        script_total=1,
    )
    dashboard.finish(exit_code=0, tool_error=None, log_path=None)
    dashboard.close()

    rendered = stream.getvalue()
    assert rendered.startswith("\x1b[?25l\x1b[0m\x1b[2J\x1b[H")
    assert rendered.endswith("\x1b[0m\x1b[?25h")
    assert rendered.count("\x1b[?25h") == 1


def test_dashboard_does_not_rewrite_unchanged_frames() -> None:
    stream = _CountingTerminal()
    dashboard = TerminalDashboard(
        stream,
        color_enabled=False,
        refresh_seconds=0.01,
        width_supplier=lambda: 60,
    )

    try:
        dashboard.begin_request(
            source_name="script.sh",
            bundle_files=(),
            script_total=1,
        )
        initial_flush_count = stream.flush_count
        time.sleep(0.05)

        assert stream.flush_count == initial_flush_count

        dashboard.begin_script(
            script_name="script.sh",
            script_index=1,
            script_total=1,
            messages=(),
            inline_files=(),
            warnings=(),
        )
        _wait_until(lambda: stream.flush_count > initial_flush_count)
        changed_flush_count = stream.flush_count
        time.sleep(0.05)

        assert stream.flush_count == changed_flush_count
    finally:
        dashboard.close()


def test_dashboard_redraws_when_terminal_width_changes() -> None:
    stream = _CountingTerminal()
    width = [60]
    dashboard = TerminalDashboard(
        stream,
        color_enabled=False,
        refresh_seconds=0.01,
        width_supplier=lambda: width[0],
    )

    try:
        dashboard.begin_request(
            source_name="script.sh",
            bundle_files=(),
            script_total=1,
        )
        initial_flush_count = stream.flush_count
        width[0] = 50
        _wait_until(lambda: stream.flush_count > initial_flush_count)

        frames = stream.getvalue()
        assert "┌" + "─" * 48 + "┐" in frames
    finally:
        dashboard.close()


def test_application_supplies_messages_and_inline_files_to_presentation(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "presented-script.txt"
    script_path.write_text(
        "# PATCHHARBOR\n"
        "# PATCHHARBOR MESSAGE commit.last START\n"
        "# Parser updated\n"
        "# PATCHHARBOR MESSAGE commit.last END\n"
        "# PATCHHARBOR FILE note.txt START\n"
        "# payload\n"
        "# PATCHHARBOR FILE note.txt END\n",
        encoding="utf-8",
    )
    presentation = _RecordingPresentation()

    result = run_script_path(
        script_path,
        cwd=tmp_path,
        timeout_seconds=2,
        selection_input=StringIO(),
        selection_output=StringIO(),
        output=OutputTargets(visible_text_stream=StringIO()),
        presentation=presentation,
    )

    assert result == 0
    assert presentation.request == {
        "source_name": str(script_path),
        "bundle_files": (),
        "script_total": 1,
        "warnings": (),
    }
    assert presentation.script is not None
    assert presentation.script["script_name"] == str(script_path)
    assert presentation.script["script_index"] == 1
    assert presentation.script["script_total"] == 1
    assert presentation.script["messages"] == (("commit.last", "Parser updated"),)
    assert presentation.script["inline_files"] == (
        PresentedFile(
            name="note.txt",
            size_bytes=7,
            kind="FILE",
        ),
    )
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "payload"
