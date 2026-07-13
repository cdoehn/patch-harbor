"""Script input and orchestration for PatchHarbor."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TextIO

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker



@dataclass(frozen=True)
class ScriptSource:
    """Neutral script input handed to the parsing and execution pipeline."""

    text: str
    suffix: str


def read_script_file(script_path: Path) -> ScriptSource:
    """Read one UTF-8 script file into a neutral source value."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source {script_path}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    return ScriptSource(
        text=script_text,
        suffix=script_path.suffix,
    )


def read_script_stdin(stream: TextIO) -> ScriptSource:
    """Read standard input once into a neutral source value."""
    try:
        script_text = stream.read()
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source standard input: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    if not script_text:
        raise PatchHarborError(
            "no script input received",
            ExitCode.USAGE_ERROR,
        )

    return ScriptSource(
        text=script_text,
        suffix=".ps1" if os.name == "nt" else ".sh",
    )


def run_script_source(
    source: ScriptSource,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Validate and run one neutral script source."""
    try:
        validate_required_marker(source.text)
    except ScriptFormatError as exc:
        raise PatchHarborError(
            str(exc),
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    try:
        with temporary_script_file(source.text, suffix=source.suffix) as temporary_path:
            return execute_script_file(
                temporary_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc

def _directory_script_paths(directory: Path) -> list[Path]:
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise PatchHarborError(
            f"cannot read script source directory {directory}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    candidates: list[tuple[int, str, Path]] = []
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_file():
                continue
            source = read_script_file(entry)
            validate_required_marker(source.text)
            modified_ns = entry.stat().st_mtime_ns
        except (PatchHarborError, ScriptFormatError, OSError):
            continue
        candidates.append((modified_ns, entry.name, entry))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, _, path in candidates]


def _select_directory_script(
    candidates: list[Path],
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> Path:
    if len(candidates) == 1:
        return candidates[0]

    print("Available PatchHarbor scripts:", file=output_stream)
    for index, candidate in enumerate(candidates, start=1):
        print(f"  {index}. {candidate.name}", file=output_stream)

    while True:
        print(
            f"Choose one script by number [1-{len(candidates)}]: ",
            end="",
            file=output_stream,
            flush=True,
        )
        line = input_stream.readline()
        if line == "" or line.strip() == "":
            raise PatchHarborError(
                "no script selected",
                ExitCode.USAGE_ERROR,
            )

        value = line.strip()
        if value.isascii() and value.isdecimal():
            selected_index = int(value)
            if 1 <= selected_index <= len(candidates):
                return candidates[selected_index - 1]

        print(
            f"Invalid selection. Enter an ASCII number from 1 to {len(candidates)}.",
            file=output_stream,
        )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
) -> int:
    """Run a script file or select one direct script from a directory."""
    selected_path = path
    if path.is_dir():
        candidates = _directory_script_paths(path)
        if not candidates:
            raise PatchHarborError(
                f"no PatchHarbor scripts found in directory {path}",
                ExitCode.NO_VALID_SCRIPT,
            )
        selected_path = _select_directory_script(
            candidates,
            input_stream=selection_input,
            output_stream=selection_output,
        )

    source = read_script_file(selected_path)
    return run_script_source(
        source,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )

