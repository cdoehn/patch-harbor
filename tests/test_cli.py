from __future__ import annotations

from io import StringIO
from pathlib import Path

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


def test_version_flag_reports_release_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert capsys.readouterr().out == "patchharbor 1.0.0\n"


def test_run_help_is_the_complete_public_command_reference(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["fs", "run", "--help"])

    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "# PATCHHARBOR",
        "ZIP PatchBundles may contain ordered scripts and byte-exact payload files.",
        "Scripts run in the current working directory.",
        "--timeout SECONDS",
        "--plain",
        "--no-color",
        "--log",
    ):
        assert expected in help_text


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
        assert observed_output.warning_text_stream is stderr
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


def test_interactive_terminal_wires_dashboard_and_restores_terminal(
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
        assert output.warning_text_stream is None
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
    assert rendered.count("\x1b[?25l") == 1
    assert rendered.count("\x1b[?25h") == 1
    assert "\x1b[2J\x1b[H" in rendered
    assert rendered.index("\x1b[?25l") < rendered.index("SOURCE")
    assert rendered.rindex("status: success") < rendered.rindex("\x1b[?25h")
    for section in ("SOURCE", "MESSAGES", "FILES", "EXECUTION", "RESULT"):
        assert section in rendered
    assert "running-two" in rendered
    for color_sequence in (
        "\x1b[1;36m",
        "\x1b[1;34m",
        "\x1b[1;32m",
        "\x1b[1;33m",
        "\x1b[1;31m",
        "\x1b[2m",
    ):
        assert color_sequence not in rendered
    assert stderr.getvalue() == ""



def test_too_narrow_terminal_falls_back_to_plain_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        assert options["presentation"] is None
        output = options["output"]
        assert isinstance(output, OutputTargets)
        assert output.live_text_stream is stdout
        output.live_text_stream.write("narrow-fallback\n")
        return 0

    monkeypatch.setattr(cli, "terminal_supports_dashboard", lambda stream: False)
    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    result = main(
        ["fs", "run", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stdout.getvalue() == "narrow-fallback\n"
    assert stderr.getvalue() == ""


def test_keyboard_interrupt_restores_terminal_and_returns_130(
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
        assert presentation is not None
        presentation.begin_request(
            source_name=str(path),
            bundle_files=(),
            script_total=1,
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "terminal_supports_dashboard", lambda stream: True)
    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    result = main(
        ["fs", "run", "--no-color", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    rendered = stdout.getvalue()
    assert result == 130
    assert "status: error · exit code: 130" in rendered
    assert "request aborted by user" in rendered
    assert rendered.endswith("\x1b[0m\x1b[?25h")
    assert stderr.getvalue() == ""


def test_unexpected_exception_still_restores_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        presentation = options["presentation"]
        assert presentation is not None
        presentation.begin_request(
            source_name=str(path),
            bundle_files=(),
            script_total=1,
        )
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cli, "terminal_supports_dashboard", lambda stream: True)
    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    with pytest.raises(RuntimeError, match="unexpected"):
        main(
            ["fs", "run", "--no-color", str(tmp_path / "script.sh")],
            stdin=StringIO(),
            stdout=stdout,
            stderr=StringIO(),
        )

    assert stdout.getvalue().endswith("\x1b[0m\x1b[?25h")


def test_output_os_error_uses_platform_neutral_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        raise PermissionError("native platform wording")

    monkeypatch.setattr(cli, "run_script_path", fake_run_script_path)

    result = main(
        ["fs", "run", "--plain", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert result == 7
    assert stderr.getvalue() == (
        "patchharbor: cannot write PatchHarbor output: permission denied\n"
    )


class _ReconfigurableStream(StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.reconfigure_calls: list[dict[str, str]] = []

    def reconfigure(self, **options: str) -> None:
        self.reconfigure_calls.append(options)


def test_real_standard_streams_are_configured_for_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdin = _ReconfigurableStream()
    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    monkeypatch.setattr(cli.sys, "stdin", stdin)
    monkeypatch.setattr(cli.sys, "stdout", stdout)
    monkeypatch.setattr(cli.sys, "stderr", stderr)

    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert stdin.reconfigure_calls == [
        {"encoding": "utf-8", "errors": "strict"}
    ]
    assert stdout.reconfigure_calls == [
        {"encoding": "utf-8", "errors": "replace"}
    ]
    assert stderr.reconfigure_calls == [
        {"encoding": "utf-8", "errors": "replace"}
    ]
