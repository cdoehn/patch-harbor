from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

import patchharbor.cli as cli
from patchharbor.cli import main
from patchharbor.output import OutputTargets
from patchharbor.presentation import PresentedFile
from patchharbor.run_report import ResultBundleStatus


class _TerminalInput(StringIO):
    def isatty(self) -> bool:
        return True


class _TerminalOutput(StringIO):
    def isatty(self) -> bool:
        return True


@pytest.mark.parametrize(
    "command",
    (
        "websocket",
        "clipboard",
        "ssh",
        "save",
        "test",
        "testmanager",
        "commit",
        "plugin",
        "watch",
        "repo-assist",
        "promptbridge",
    ),
)
def test_non_core_orchestration_commands_are_not_public(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main([command])

    assert raised.value.code == 2
    capsys.readouterr()


@pytest.mark.parametrize(
    "arguments",
    (
        ("register", "--new", "missing-repository"),
        ("registry", "list", "--js"),
        ("context", "--js", "missing-repository"),
        ("bundle", "--out", "results", "missing-repository"),
        ("apply", "--dry", "missing-package.zip"),
        ("fs", "run", "--pla", "missing-script.sh"),
    ),
)
def test_public_cli_rejects_abbreviated_options(
    arguments: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(list(arguments))

    assert raised.value.code == 2
    capsys.readouterr()


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


def test_apply_plain_sanitizes_child_output_without_dashboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()
    report = SimpleNamespace(warnings=())

    def fake_run_apply_path(_path: Path, **options: object) -> object:
        assert options["presentation"] is None
        output = options["output"]
        assert isinstance(output, OutputTargets)
        assert output.line_observer is None
        assert output.live_text_stream is not stdout
        output.live_text_stream.write("safe\x1b[31m-red\x1b[0m\x08\n")
        return report

    monkeypatch.setattr(cli, "run_apply_path", fake_run_apply_path)
    monkeypatch.setattr(
        cli,
        "_write_apply_completion",
        lambda _report, **_options: 0,
    )

    result = main(
        ["apply", "--plain", str(tmp_path / "patch.zip")],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stdout.getvalue() == "safe-red\n"
    assert "\x1b" not in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_apply_returns_tool_error_when_dashboard_cannot_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()
    application_continued = False

    class BrokenDashboard:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def begin_request(self, **_values: object) -> None:
            raise OSError("dashboard unavailable")

        def update_output(self, *_values: object) -> None:
            raise AssertionError("output must not be observed before begin_request")

        def close(self) -> None:
            pass

    def fake_run_apply_path(_path: Path, **options: object) -> object:
        nonlocal application_continued
        presentation = options["presentation"]
        presentation.begin_request(
            source_name="patch.zip",
            bundle_files=(),
            script_total=1,
        )
        application_continued = True
        raise AssertionError("application continued after presentation failure")

    monkeypatch.setattr(cli, "terminal_supports_dashboard", lambda _stream: True)
    monkeypatch.setattr(cli, "TerminalDashboard", BrokenDashboard)
    monkeypatch.setattr(cli, "run_apply_path", fake_run_apply_path)

    result = main(
        ["apply", str(tmp_path / "patch.zip")],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 7
    assert not application_continued
    assert "\x1b" not in stdout.getvalue()


def test_apply_tty_uses_repository_dashboard_without_color(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()
    result_path = tmp_path / "results" / "result.zip"
    report = SimpleNamespace(
        warnings=(),
        completion_tool_error=None,
        process_exit_code=0,
        result_bundle=SimpleNamespace(
            path=result_path,
            status=ResultBundleStatus.CREATED,
            emergency_diagnostics_path=None,
        ),
    )

    monkeypatch.setattr(cli, "terminal_supports_dashboard", lambda _stream: True)

    def fake_run_apply_path(_path: Path, **options: object) -> object:
        presentation = options["presentation"]
        output = options["output"]
        assert presentation is not None
        assert isinstance(output, OutputTargets)
        assert output.live_text_stream is None
        assert output.line_observer is not None
        presentation.begin_request(
            source_name="patch.zip",
            repository_name="resolving…",
            repository_context="repo_id: 1111",
            bundle_files=(),
            script_total=1,
        )
        presentation.update_repository(
            repository_name=str(tmp_path / "work" / "repository"),
            repository_context="repo_id: 1111 · base: abcdef · state: 0123",
        )
        presentation.begin_script(
            script_name="run.sh",
            script_index=1,
            script_total=1,
            messages=(("commit.last", "Apply integrated"),),
            warnings=(),
        )
        output.line_observer(("visible\x1b[31m-red\x1b[0m\n",), 0)
        return report

    monkeypatch.setattr(cli, "run_apply_path", fake_run_apply_path)

    result = main(
        ["apply", "--no-color", str(tmp_path / "patch.zip")],
        stdout=stdout,
        stderr=stderr,
    )

    rendered = stdout.getvalue()
    assert result == 0
    assert rendered.count("\x1b[?25l") == 1
    assert rendered.count("\x1b[?25h") == 1
    assert "\x1b[31m-red" not in rendered
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
    assert rendered.index("\x1b[?25l") < rendered.rindex("\x1b[?25h")
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
    assert rendered.count("\x1b[?25l") == 1
    assert rendered.count("\x1b[?25h") == 1
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
