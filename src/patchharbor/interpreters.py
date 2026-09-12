"""Deterministic selection and resolution of supported interpreters."""

from __future__ import annotations

from codecs import BOM_UTF8
from dataclasses import dataclass
from pathlib import Path

from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.platform.runtime import find_executable, is_windows


@dataclass(frozen=True, slots=True)
class InterpreterSpec:
    """One supported interpreter before executable lookup."""

    executable: str
    script_suffix: str
    arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedInterpreter:
    """One selected interpreter together with its resolved executable path."""

    spec: InterpreterSpec
    executable_path: str


_POWERSHELL_ARGUMENTS = ("-NoLogo", "-NoProfile", "-NonInteractive", "-File")

_BASH = InterpreterSpec(
    executable="bash",
    script_suffix=".sh",
    arguments=(),
)
_WINDOWS_POWERSHELL = InterpreterSpec(
    executable="powershell.exe",
    script_suffix=".ps1",
    arguments=_POWERSHELL_ARGUMENTS,
)
_POWERSHELL_7 = InterpreterSpec(
    executable="pwsh",
    script_suffix=".ps1",
    arguments=_POWERSHELL_ARGUMENTS,
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
        return _WINDOWS_POWERSHELL if is_windows(os_name=os_name) else _BASH

    interpreter = _SUPPORTED_SHEBANGS.get(first_line)
    if interpreter is None:
        requested = first_line[2:] or "<empty>"
        raise PatchHarborError(
            f"unsupported script interpreter in shebang: {requested}",
            FailureReason.INTERPRETER_ERROR,
        )
    return interpreter


def resolve_interpreter(spec: InterpreterSpec) -> str:
    """Resolve a selected interpreter executable through the system PATH."""
    executable_path = find_executable(spec.executable)
    if executable_path is None:
        raise PatchHarborError(
            f"script interpreter not found: {spec.executable}",
            FailureReason.INTERPRETER_ERROR,
        )
    return executable_path


def resolve_script_interpreter(
    script_text: str,
    *,
    os_name: str | None = None,
) -> ResolvedInterpreter:
    """Select and resolve the fixed interpreter for one script."""
    spec = select_interpreter(script_text, os_name=os_name)
    return ResolvedInterpreter(
        spec=spec,
        executable_path=resolve_interpreter(spec),
    )


def encode_script_file(script_text: str, spec: InterpreterSpec) -> bytes:
    """Encode one private script for the selected interpreter."""
    encoded = script_text.encode("utf-8")
    if spec.executable.casefold() == "powershell.exe":
        return BOM_UTF8 + encoded
    return encoded


def build_interpreter_command(
    spec: InterpreterSpec,
    executable_path: str,
    script_path: Path,
) -> list[str]:
    """Build fixed process arguments without interpreting arbitrary shebang text."""
    return [executable_path, *spec.arguments, str(script_path)]
