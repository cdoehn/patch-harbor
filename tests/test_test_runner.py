"""Behavioral contracts of the development test launcher, not its output."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import run_tests as runner
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
