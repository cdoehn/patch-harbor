"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError


DEFAULT_TIMEOUT_SECONDS = 300.0

_BASH = "bash"
_WINDOWS_POWERSHELL = "windows-powershell"
_POWERSHELL_7 = "powershell-7"

_SUPPORTED_SHEBANGS = {
    "#!/bin/bash": _BASH,
    "#!/usr/bin/bash": _BASH,
    "#!/usr/bin/env bash": _BASH,
    "#!powershell": _WINDOWS_POWERSHELL,
    "#!powershell.exe": _WINDOWS_POWERSHELL,
    "#!/usr/bin/env powershell": _WINDOWS_POWERSHELL,
    "#!/usr/bin/env powershell.exe": _WINDOWS_POWERSHELL,
    "#!pwsh": _POWERSHELL_7,
    "#!pwsh.exe": _POWERSHELL_7,
    "#!/usr/bin/pwsh": _POWERSHELL_7,
    "#!/usr/bin/env pwsh": _POWERSHELL_7,
    "#!/usr/bin/env pwsh.exe": _POWERSHELL_7,
}

_INTERPRETER_EXECUTABLES = {
    _BASH: "bash",
    _WINDOWS_POWERSHELL: "powershell.exe",
    _POWERSHELL_7: "pwsh",
}

_INTERPRETER_SUFFIXES = {
    _BASH: ".sh",
    _WINDOWS_POWERSHELL: ".ps1",
    _POWERSHELL_7: ".ps1",
}


@contextmanager
def _temporary_script_file(script_text: str, *, suffix: str) -> Iterator[Path]:
    """Write script text to a secure system-temp file and remove it afterwards."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=suffix,
        text=True,
    )
    script_path = Path(raw_path)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(script_text)
        yield script_path
    finally:
        script_path.unlink(missing_ok=True)


def _requested_interpreter(script_text: str) -> str:
    first_line = script_text.splitlines()[0] if script_text else ""
    if not first_line.startswith("#!"):
        return _WINDOWS_POWERSHELL if os.name == "nt" else _BASH

    interpreter = _SUPPORTED_SHEBANGS.get(first_line)
    if interpreter is None:
        requested = first_line[2:] or "<empty>"
        raise PatchHarborError(
            f"unsupported script interpreter in shebang: {requested}",
            ExitCode.INTERPRETER_ERROR,
        )
    return interpreter


def _interpreter_path(interpreter: str) -> str:
    executable = _INTERPRETER_EXECUTABLES[interpreter]
    resolved = shutil.which(executable)
    if resolved is None:
        raise PatchHarborError(
            f"script interpreter not found: {executable}",
            ExitCode.INTERPRETER_ERROR,
        )
    return resolved


def _interpreter_command(
    interpreter: str,
    executable: str,
    script_path: Path,
) -> list[str]:
    if interpreter == _BASH:
        return [executable, str(script_path)]
    return [
        executable,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(script_path),
    ]


def execute_script_text(
    script_text: str,
    *,
    suffix: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Stage and execute script text with a supported interpreter."""
    del suffix  # The source suffix never selects the interpreter.
    interpreter = _requested_interpreter(script_text)
    executable = _interpreter_path(interpreter)
    temporary_suffix = _INTERPRETER_SUFFIXES[interpreter]

    try:
        with _temporary_script_file(
            script_text,
            suffix=temporary_suffix,
        ) as script_path:
            return execute_script_file(
                script_path,
                interpreter=interpreter,
                executable=executable,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


def execute_script_file(
    script_path: Path,
    *,
    interpreter: str,
    executable: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Run one staged script with an already selected interpreter."""
    command = _interpreter_command(interpreter, executable, script_path)

    try:
        completed = subprocess.run(
            command,
            check=False,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchHarborError(
            f"script timed out after {timeout_seconds:g} seconds",
            ExitCode.TIMEOUT,
        ) from exc
    except OSError as exc:
        raise PatchHarborError(
            f"cannot start script interpreter: {exc}",
            ExitCode.INTERPRETER_ERROR,
        ) from exc

    return completed.returncode
