"""Shared values, subprocess helpers, and reasons for platform tests."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
    timeout_seconds: float = 20,
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI in text mode with stable test defaults."""
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
    timeout_seconds: float = 20,
) -> subprocess.CompletedProcess[bytes]:
    """Run the real CLI with byte input for binary transport tests."""
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
    timeout_seconds: float = 20,
) -> subprocess.CompletedProcess[str]:
    """Run the public file-system command against one source path."""
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
