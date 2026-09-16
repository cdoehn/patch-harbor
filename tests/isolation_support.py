"""Isolation shared by serial tests and independent xdist workers."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
import os
from pathlib import Path
import random
import signal
import sys
import tempfile

import pytest


class ProcessStateLeak(AssertionError):
    """A test leaked mutable process state into the next test."""


def _environment_snapshot() -> dict[str, str]:
    # pytest itself updates this variable between setup/call/teardown.
    return {name: value for name, value in os.environ.items() if name != "PYTEST_CURRENT_TEST"}


@contextmanager
def assert_process_state_restored() -> Iterator[None]:
    """Fail on a leak, then restore baseline state so a worker can continue.

    Normal lazy library imports are allowed. Deliberate edits to sys.modules
    must use monkeypatch or a child process, not an indiscriminate module purge.
    """
    cwd = Path.cwd()
    environment = _environment_snapshot()
    path = sys.path[:]
    random_state = random.getstate()
    handlers = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        leaks = []
        try:
            current_cwd = Path.cwd()
        except OSError:
            current_cwd = None
        if current_cwd != cwd:
            leaks.append("cwd")
            os.chdir(cwd)
        if _environment_snapshot() != environment:
            leaks.append("environment")
            current = os.environ.get("PYTEST_CURRENT_TEST")
            os.environ.clear()
            os.environ.update(environment)
            if current is not None:
                os.environ["PYTEST_CURRENT_TEST"] = current
        if sys.path != path:
            leaks.append("sys.path")
            sys.path[:] = path
        if random.getstate() != random_state:
            leaks.append("random")
            random.setstate(random_state)
        for number, handler in handlers.items():
            if signal.getsignal(number) != handler:
                leaks.append(f"signal:{number}")
                signal.signal(number, handler)
        if leaks:
            raise ProcessStateLeak(", ".join(leaks))


@pytest.fixture(autouse=True)
def process_state_guard() -> Iterator[None]:
    with assert_process_state_restored():
        yield


@pytest.fixture(autouse=True)
def isolated_test_environment(process_state_guard, monkeypatch, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Each test, including its subprocesses, gets separate user/Git/temp data."""
    # Do not prepopulate tmp_path: empty-workspace tests depend on it.
    root = tmp_path_factory.mktemp("user-environment")
    directories = {
        "HOME": root / "home", "USERPROFILE": root / "home",
        "XDG_CONFIG_HOME": root / "config", "XDG_STATE_HOME": root / "state",
        "XDG_CACHE_HOME": root / "cache", "APPDATA": root / "appdata",
        "LOCALAPPDATA": root / "localappdata",
        "TMPDIR": root / "tmp", "TEMP": root / "tmp", "TMP": root / "tmp",
    }
    for name, path in directories.items():
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(name, str(path))
    monkeypatch.setattr(tempfile, "tempdir", str(directories["TMPDIR"]))
    # Test commits must never use the caller's worktree/index, signing settings,
    # global excludes or system/user hooks. Local test-repository config wins.
    for name in tuple(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    return root
