"""Shared values, subprocess helpers, and reasons for platform tests."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import TypeVar

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"
IS_WINDOWS = os.name == "nt"

REQUIRES_POSIX_SPECIAL_FILES = pytest.mark.skipif(
    IS_WINDOWS,
    reason="requires POSIX special-file support",
)
REQUIRES_BASH_DOCKER_RUNNER = pytest.mark.skipif(
    IS_WINDOWS,
    reason="requires the Bash-based Docker integration runner",
)
REQUIRES_POWERSHELL_7 = pytest.mark.skipif(
    shutil.which("pwsh") is None,
    reason="requires the PowerShell 7 executable 'pwsh'",
)

_T = TypeVar("_T")


def native_value(posix: _T, windows: _T) -> _T:
    """Return the current platform's value while keeping variants adjacent."""
    return windows if IS_WINDOWS else posix


def native_script(posix_body: str, windows_body: str) -> str:
    """Build one marker-valid script from the current platform body."""
    body = native_value(posix_body, windows_body).rstrip("\n")
    return f"{REQUIRED_MARKER}\n{body}\n"


def normalized_path(path: str | Path) -> str:
    """Return the native comparison form of one absolute path."""
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def project_environment(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment importing PatchHarbor from this checkout."""
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )
    if overrides:
        environment.update(overrides)
    return environment


def run_cli(
    cwd: Path,
    *arguments: str,
    environment_overrides: Mapping[str, str] | None = None,
    input_text: str | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI without an arbitrary functional-test deadline.

    A caller testing timeout/lifecycle behavior may pass an explicit bound.
    Disabling pytest-timeout alone does not disable subprocess.run's timeout.
    """
    standard_input = (
        {"stdin": subprocess.DEVNULL}
        if input_text is None
        else {"input": input_text}
    )
    return subprocess.run(
        [sys.executable, "-m", "patchharbor.cli", *arguments],
        cwd=cwd,
        env=project_environment(environment_overrides),
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        timeout=timeout_seconds,
        check=False,
        **standard_input,
    )


def run_cli_bytes(
    cwd: Path,
    *arguments: str,
    input_bytes: bytes,
    environment_overrides: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run binary transport tests, unbounded unless explicitly requested."""
    return subprocess.run(
        [sys.executable, "-m", "patchharbor.cli", *arguments],
        cwd=cwd,
        env=project_environment(environment_overrides),
        capture_output=True,
        input=input_bytes,
        timeout=timeout_seconds,
        check=False,
    )


def run_patchharbor(
    source_path: Path,
    *,
    cwd: Path,
    environment_overrides: Mapping[str, str] | None = None,
    arguments: tuple[str, ...] = (),
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a functional file-system test, preserving any explicit deadline."""
    return run_cli(
        cwd,
        "fs",
        "run",
        *arguments,
        str(source_path),
        environment_overrides=environment_overrides,
        timeout_seconds=timeout_seconds,
    )


def log_path_from_stderr(stderr: str) -> Path:
    """Extract the temporary PatchHarbor log path from plain stderr."""
    prefix = "patchharbor: log: "
    matching = [line for line in stderr.splitlines() if line.startswith(prefix)]
    assert matching, stderr
    return Path(matching[-1].removeprefix(prefix))


def wait_for_child_pid(ready_path: Path, *, timeout: float = 5.0) -> int:
    """Wait until one test process publishes its PID."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready_path.exists():
            value = ready_path.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
        time.sleep(0.02)
    raise AssertionError(f"child PID was not written to {ready_path}")


def _pid_is_running(pid: int) -> bool:
    if not IS_WINDOWS:
        stat_path = Path(f"/proc/{pid}/stat")
        try:
            fields = stat_path.read_text(encoding="utf-8").split()
        except FileNotFoundError:
            return False
        if len(fields) > 2 and fields[2] == "Z":
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _kill_test_pid(pid: int) -> None:
    if not _pid_is_running(pid):
        return
    if not IS_WINDOWS:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        return

    import ctypes
    from ctypes import wintypes

    process_terminate = 0x0001
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_terminate, False, pid)
    if handle:
        try:
            kernel32.TerminateProcess(handle, 1)
        finally:
            kernel32.CloseHandle(handle)


def assert_child_process_stopped(pid: int, *, timeout: float = 5.0) -> None:
    """Assert that one test child exits, cleaning it up on failure."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_is_running(pid):
            return
        time.sleep(0.05)
    _kill_test_pid(pid)
    raise AssertionError(f"child process {pid} survived PatchHarbor")


def cleanup_test_processes(*process_ids: int | None) -> None:
    """Best-effort cleanup for child processes created by lifecycle tests."""
    for process_id in reversed(process_ids):
        if process_id is not None:
            _kill_test_pid(process_id)


def create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    """Create one symlink or skip with one stable cross-platform reason."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        pytest.skip("requires symlink creation permission on this platform")
