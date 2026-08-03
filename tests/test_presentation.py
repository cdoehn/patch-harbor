from __future__ import annotations

from io import StringIO
from pathlib import Path

from patchharbor.application import run_script_path
from patchharbor.output import OutputTargets
from patchharbor.presentation import (
    DashboardSnapshot,
    PresentedFile,
    render_dashboard,
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
    assert all(len(line) == 60 for line in lines)
    for section in ("SOURCE", "MESSAGES", "FILES", "EXECUTION", "RESULT"):
        assert section in frame
    assert "weitere Messages" in frame
    assert "weitere Dateien" in frame
    assert "line-5" in frame
    assert "status: running" in frame


def test_dashboard_renderer_uses_actual_width_below_eighty() -> None:
    frame = render_dashboard(
        DashboardSnapshot(source_name="source", status="success", exit_code=0),
        width=47,
    )

    assert all(len(line) == 47 for line in frame.splitlines())
    assert "status: success" in frame


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
