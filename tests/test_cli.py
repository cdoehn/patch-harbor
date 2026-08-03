from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

import patchharbor.cli as cli
from patchharbor.cli import main
from patchharbor.output import OutputTargets


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
