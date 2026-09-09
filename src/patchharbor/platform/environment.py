"""Collect a small, best-effort allowlist of local runtime facts, never secrets."""

from __future__ import annotations

import os
from pathlib import PureWindowsPath, PurePosixPath
import platform
import re
import subprocess
import tempfile
from collections.abc import Callable

from patchharbor.platform.runtime import find_executable, is_windows


_UV_PROBE_TIMEOUT_SECONDS = 2
_MAX_VALUE_CHARACTERS = 256


def _text(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > _MAX_VALUE_CHARACTERS:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    return value


def _fact(probe: Callable[[], str]) -> str | None:
    try:
        return _text(probe())
    except (OSError, RuntimeError, ValueError):
        return None


def _kernel_release() -> str | None:
    # Python's platform.release() may report Android/iOS *OS* versions rather
    # than the kernel. Select only uname.release; never retain its node field.
    if hasattr(os, "uname"):
        return _fact(lambda: os.uname().release)
    return _fact(platform.release)


def _uv_version() -> str | None:
    """Probe once, without a shell or network; discard arbitrary tool output."""
    try:
        executable = find_executable("uv")
        if executable is None:
            return None
        # Spool to a private file rather than retaining unbounded stdout in RAM.
        with tempfile.TemporaryFile() as output:
            completed = subprocess.run(
                [executable, "--version"],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
                cwd=tempfile.gettempdir(),
                check=False,
                timeout=_UV_PROBE_TIMEOUT_SECONDS,
            )
            if completed.returncode != 0:
                return None
            output.seek(0)
            value = output.read(513)
        if len(value) > 512:
            return None
        match = re.fullmatch(
            rb"uv ([0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*))(?: \([^\r\n]*\))?\r?\n?",
            value,
        )
        return match.group(1).decode("ascii") if match is not None else None
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return None


def capture_runtime_environment() -> dict[str, object]:
    """Return fresh facts about the running interpreter's OS, not a guessed host."""
    system = _fact(platform.system)
    distribution: dict[str, str | None] = {
        "id": None, "name": None, "version_id": None,
    }
    if system == "Linux":
        try:
            release = platform.freedesktop_os_release()
        except (OSError, RuntimeError, ValueError):
            release = {}
        # /etc/os-release describes the userland, including Ubuntu inside proot.
        # Never serialize the complete document or platform.uname()/platform().
        distribution = {
            "id": _text(release.get("ID")),
            "name": _text(release.get("PRETTY_NAME", release.get("NAME"))),
            "version_id": _text(release.get("VERSION_ID")),
        }
    elif system == "Android":
        distribution = {"id": "android", "name": "Android", "version_id": _fact(platform.release)}
    elif system == "Windows":
        distribution = {"id": "windows", "name": "Windows", "version_id": _fact(platform.release)}
    elif system == "Darwin":
        distribution = {"id": "macos", "name": "macOS", "version_id": _fact(lambda: platform.mac_ver()[0])}

    shell_variable = "COMSPEC" if is_windows() else "SHELL"
    shell_value = _text(os.environ.get(shell_variable))
    shell_path_type = PureWindowsPath if is_windows() else PurePosixPath
    shell = shell_path_type(shell_value).name if shell_value is not None else None
    return {
        "system": system,
        "distribution": distribution,
        "kernel": _kernel_release(),
        "architecture": _fact(platform.machine),
        "python_version": _fact(platform.python_version),
        "python_implementation": _fact(platform.python_implementation),
        "uv_version": _uv_version(),
        "configured_shell": shell,
        "shell_source": shell_variable if shell is not None else None,
    }
