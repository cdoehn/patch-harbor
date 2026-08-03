from __future__ import annotations

from io import StringIO
from pathlib import Path
import time

import pytest

import patchharbor.cli as cli
from patchharbor.cli import main
from patchharbor.output import OutputTargets
from patchharbor.presentation import PresentedFile


class _TerminalInput(StringIO):
    def isatty(self) -> bool:
        return True


class _TerminalOutput(StringIO):
    def isatty(self) -> bool:
        return True


def test_fs_run_without_path_on_terminal_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["fs", "run"], stdin=_TerminalInput())

    assert raised.value.code == 2
    assert "PATH is required when standard input is a terminal" in capsys.readouterr().err


def test_plain_flag_streams_to_an_interactive_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()
    observed_output: OutputTargets | None = None

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        nonlocal observed_output
        observed_output = options["output"]
        assert observed_output.live_text_stream is stdout
        observed_output.live_text_stream.write("plain-output\n")
        return 0

    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    result = main(
        ["fs", "run", "--plain", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stdout.getvalue() == "plain-output\n"
    assert stderr.getvalue() == ""


def test_interactive_terminal_uses_fixed_dashboard_and_periodic_redraw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        presentation = options["presentation"]
        output = options["output"]
        assert presentation is not None
        presentation.begin_request(
            source_name=str(path),
            bundle_files=(
                PresentedFile(
                    name="asset.bin",
                    size_bytes=3,
                    kind="bundle",
                ),
            ),
            script_total=1,
        )
        presentation.begin_script(
            script_name="apply.sh",
            script_index=1,
            script_total=1,
            messages=(("commit.next", "Add terminal dashboard"),),
            inline_files=(),
            warnings=(),
        )
        assert output.line_observer is not None
        output.line_observer(("running-one\n",), 0)
        time.sleep(0.45)
        output.line_observer(("running-one\n", "running-two\n"), 0)
        return 0

    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    result = main(
        ["fs", "run", "--no-color", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    rendered = stdout.getvalue()
    assert result == 0
    assert rendered.startswith("\x1b[2J\x1b[H")
    assert rendered.count("\x1b[H") >= 3
    assert "SOURCE" in rendered
    assert "MESSAGES" in rendered
    assert "FILES" in rendered
    assert "EXECUTION" in rendered
    assert "RESULT" in rendered
    assert "running-two" in rendered
    assert "status: success" in rendered
    assert stderr.getvalue() == ""
