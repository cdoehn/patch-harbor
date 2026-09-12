from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

import patchharbor.cli as cli
from patchharbor.cli import main
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


@pytest.mark.parametrize(
    ("arguments", "expected_automatic"),
    (
        (("apply", "--json"), False),
        (("apply", "--json", "--automatic"), True),
    ),
)
def test_parameterless_apply_propagates_manual_or_automatic_origin(
    monkeypatch: pytest.MonkeyPatch,
    arguments: tuple[str, ...],
    expected_automatic: bool,
) -> None:
    observed: list[tuple[Path | None, bool]] = []
    report = SimpleNamespace(warnings=())

    def fake_apply(path=None, **options):
        observed.append((path, False))
        return report

    def fake_apply_next(**options):
        observed.append((None, True))
        return report

    monkeypatch.setattr(cli.api, "apply", fake_apply)
    monkeypatch.setattr(cli.api, "apply_next", fake_apply_next)
    monkeypatch.setattr(
        cli,
        "_write_apply_completion",
        lambda _report, **_options: 0,
    )

    result = main(
        list(arguments),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert result == 0
    assert observed == [(None, expected_automatic)]


def test_internal_automatic_origin_is_hidden_and_rejects_an_explicit_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["apply", "--help"])
    assert help_exit.value.code == 0
    assert "--automatic" not in capsys.readouterr().out

    with pytest.raises(SystemExit) as path_exit:
        main(["apply", "--automatic", "patch.zip"])
    assert path_exit.value.code == 2
    assert "does not accept PATCH_ZIP" in capsys.readouterr().err


def test_fs_run_without_path_on_terminal_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["fs", "run"], stdin=_TerminalInput())

    assert raised.value.code == 2
    assert "PATH is required when standard input is a terminal" in capsys.readouterr().err


def test_keyboard_interrupt_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()
    stderr = StringIO()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.api, "run", fake_run_script_path)

    result = main(
        ["fs", "run", "--no-color", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 130
    assert stderr.getvalue() == ""


def test_unexpected_application_exception_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = _TerminalOutput()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cli.api, "run", fake_run_script_path)

    with pytest.raises(RuntimeError, match="unexpected"):
        main(
            ["fs", "run", "--no-color", str(tmp_path / "script.sh")],
            stdin=StringIO(),
            stdout=stdout,
            stderr=StringIO(),
        )


def test_output_os_error_returns_execution_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = StringIO()

    def fake_run_script_path(
        path: Path,
        **options: object,
    ) -> int:
        raise PermissionError("native platform wording")

    monkeypatch.setattr(cli.api, "run", fake_run_script_path)

    result = main(
        ["fs", "run", "--plain", str(tmp_path / "script.sh")],
        stdin=StringIO(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert result == 7


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
