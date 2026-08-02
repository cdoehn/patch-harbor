"""Deterministic selection and resolution of supported interpreters."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil

from patchharbor.errors import ExitCode, PatchHarborError


@dataclass(frozen=True)
class InterpreterSpec:
    """One supported interpreter before executable lookup."""

    name: str
    executable: str
    script_suffix: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedInterpreter:
    """One supported interpreter with an executable found on PATH."""

    spec: InterpreterSpec
    executable_path: str


_BASH = InterpreterSpec(
    name="bash",
    executable="bash",
    script_suffix=".sh",
    arguments=(),
)
_WINDOWS_POWERSHELL = InterpreterSpec(
    name="windows-powershell",
    executable="powershell.exe",
    script_suffix=".ps1",
    arguments=("-NoLogo", "-NoProfile", "-NonInteractive", "-File"),
)
_POWERSHELL_7 = InterpreterSpec(
    name="powershell-7",
    executable="pwsh",
    script_suffix=".ps1",
    arguments=("-NoLogo", "-NoProfile", "-NonInteractive", "-File"),
)

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


def select_interpreter(
    script_text: str,
    *,
    os_name: str | None = None,
) -> InterpreterSpec:
    """Select one whitelisted interpreter from the first line or OS default."""
    first_line = script_text.splitlines()[0] if script_text else ""
    if not first_line.startswith("#!"):
        platform_name = os.name if os_name is None else os_name
        return _WINDOWS_POWERSHELL if platform_name == "nt" else _BASH

    interpreter = _SUPPORTED_SHEBANGS.get(first_line)
    if interpreter is None:
        requested = first_line[2:] or "<empty>"
        raise PatchHarborError(
            f"unsupported script interpreter in shebang: {requested}",
            ExitCode.INTERPRETER_ERROR,
        )
    return interpreter


def resolve_interpreter(spec: InterpreterSpec) -> ResolvedInterpreter:
    """Resolve a selected interpreter executable through the system PATH."""
    executable_path = shutil.which(spec.executable)
    if executable_path is None:
        raise PatchHarborError(
            f"script interpreter not found: {spec.executable}",
            ExitCode.INTERPRETER_ERROR,
        )
    return ResolvedInterpreter(
        spec=spec,
        executable_path=executable_path,
    )


def build_interpreter_command(
    interpreter: ResolvedInterpreter,
    script_path: Path,
) -> list[str]:
    """Build fixed process arguments without interpreting arbitrary shebang text."""
    return [
        interpreter.executable_path,
        *interpreter.spec.arguments,
        str(script_path),
    ]
