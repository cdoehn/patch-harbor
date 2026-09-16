"""Behavioral contracts of the development test launcher, not its output."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import test_runner as runner
from tests.platform_support import PROJECT_ROOT


def test_default_invokes_all_tests_in_a_fresh_process(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main([]) == 0
    command, kwargs = calls[0]
    assert command[:3] == [sys.executable, "-m", "pytest"]
    assert command[-1] == "tests"
    assert command[command.index("-p") + 1] == "no:timeout"
    assert kwargs["cwd"] == PROJECT_ROOT
    assert kwargs["check"] is False
    assert "timeout" not in kwargs
    assert "shell" not in kwargs


@pytest.mark.parametrize("code", [0, 1, 2, 3, 4, 5])
def test_pytest_exit_code_is_preserved(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, code))
    assert runner.main(["--serial"]) == code


def test_forwarded_arguments_are_not_shell_evaluated(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: seen.append(command) or subprocess.CompletedProcess(command, 0))
    arguments = ["tests/test_cli.py", "-k", "not impossible; no shell"]
    assert runner.main(["--serial", "--", *arguments]) == 0
    assert seen[0][-len(arguments):] == arguments


def test_inherited_addopts_does_not_filter_the_reference_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_ADDOPTS", "--lf -k nowhere --session-timeout=0")
    before = os.environ.copy()
    seen = []
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: seen.append(kwargs["env"]) or subprocess.CompletedProcess(command, 0))
    assert runner.main([]) == 0
    assert seen[0]["PYTEST_ADDOPTS"] == ""
    assert dict(os.environ) == before


@pytest.mark.parametrize("arguments", [
    ["--durations", "-1"], ["--durations", "bad"],
    ["--serial", "--", "-n", "4"], ["--serial", "--", "-n4"],
    ["--", "--numprocesses=2"], ["--", "--dist=each"], ["--", "--tx", "popen"],
])
def test_invalid_modes_fail_before_starting_pytest(monkeypatch, arguments) -> None:
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid invocation started a process")
    monkeypatch.setattr(runner.subprocess, "run", unexpected)
    with pytest.raises(SystemExit) as error:
        runner.main(arguments)
    assert error.value.code == 2


def test_bad_duration_environment_is_a_usage_error(monkeypatch) -> None:
    monkeypatch.setenv("PATCHHARBOR_TEST_DURATIONS", "invalid")
    with pytest.raises(SystemExit) as error:
        runner.main([])
    assert error.value.code == 2
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    assert runner.main(["--durations", "0"]) == 0


@pytest.mark.parametrize("failure,expected", [(KeyboardInterrupt(), 130), (OSError("no process"), 3)])
def test_process_start_or_interrupt_cannot_report_success(monkeypatch, failure, expected) -> None:
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(runner.subprocess, "run", fail)
    assert runner.main([]) == expected


def test_signaled_child_is_a_nonzero_portable_status(monkeypatch) -> None:
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, -9))
    assert runner.main([]) == 137


def _real_suite(tmp_path: Path, body: str, *, config: str = "") -> tuple[subprocess.CompletedProcess[str], Path]:
    import textwrap
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "test_example.py").write_text(textwrap.dedent(body), encoding="utf-8")
    (suite / "conftest.py").write_text(textwrap.dedent(config), encoding="utf-8")
    junit = tmp_path / "report.xml"
    environment = os.environ.copy()
    environment["PYTEST_ADDOPTS"] = "--lf -k a_test_that_does_not_exist --session-timeout=0"
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools" / "run_tests.py"), "--serial", "--",
         str(suite), "--junitxml", str(junit)],
        cwd=tmp_path, env=environment, text=True, capture_output=True, check=False,
    )
    return completed, junit


@pytest.mark.parametrize("body,config,status,tag", [
    ("def test_example(): assert True", "", 0, None),
    ("def test_example(): assert False", "", 1, "failure"),
    ("def test_example(): pass", "import pytest\n@pytest.fixture(autouse=True)\ndef broken():\n    raise RuntimeError('setup')", 1, "error"),
    ("def test_example(): pass", "import pytest\n@pytest.fixture(autouse=True)\ndef broken():\n    yield\n    raise RuntimeError('teardown')", 1, "error"),
    ("import pytest\ndef test_example(): pytest.skip('intentional probe')", "", 0, "skipped"),
    ("import unittest\nclass TestProbe(unittest.TestCase):\n    def test_example(self):\n        with self.subTest(value=1):\n            self.assertEqual(1, 2)", "", 1, "failure"),
])
def test_real_pytest_results_survive_launcher(tmp_path, body, config, status, tag) -> None:
    from xml.etree import ElementTree
    completed, junit = _real_suite(tmp_path, body, config=config)
    assert completed.returncode == status, completed.stdout + completed.stderr
    document = ElementTree.parse(junit)
    assert document.findall(".//testcase")
    if tag is not None:
        assert document.findall(f".//{tag}")
    else:
        assert not document.findall(".//failure")
        assert not document.findall(".//error")


def test_empty_collection_is_not_a_successful_suite(tmp_path) -> None:
    completed, _ = _real_suite(tmp_path, "# no test functions\n")
    assert completed.returncode == 5


@pytest.mark.parametrize("arguments,count", [
    ([], "0"), (["--serial"], "0"), (["--workers", "2"], "2"),
    (["--workers", "4"], "4"), (["--workers", "auto"], "auto"),
])
def test_worker_selection_is_delegated_to_xdist(arguments, count) -> None:
    command, environment = runner.prepare_invocation(arguments, environment={})
    assert command[command.index("-n") + 1] == count
    assert "--max-worker-restart=0" in command
    assert environment["PYTEST_ADDOPTS"] == ""


@pytest.mark.parametrize("arguments", [
    ["--workers", "0"], ["--workers", "-2"], ["--workers", "oops"],
    ["--serial", "--workers", "2"],
])
def test_invalid_worker_selection_is_a_usage_error(arguments) -> None:
    with pytest.raises(SystemExit) as error:
        runner.prepare_invocation(arguments, environment={})
    assert error.value.code == 2
