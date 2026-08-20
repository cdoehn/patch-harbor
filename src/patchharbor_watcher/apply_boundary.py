"""Public subprocess boundary used by the separate PatchHarbor Watcher."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess
from typing import NoReturn

from patchharbor_watcher.loop import ApplyCompletion


DEFAULT_APPLY_COMMAND = ("patchharbor",)


def _reject_nonfinite_json(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON value: {value}")


def _parse_apply_response(stdout: bytes) -> tuple[dict[str, object] | None, str | None]:
    try:
        response_text = stdout.decode("utf-8")
        candidate = json.loads(
            response_text,
            parse_constant=_reject_nonfinite_json,
        )
    except (UnicodeDecodeError, ValueError):
        return None, stdout.decode("utf-8", errors="replace")
    if not isinstance(candidate, dict):
        return None, response_text
    return candidate, None


def delegate_to_apply(
    path: Path,
    *,
    apply_command: Sequence[str] = DEFAULT_APPLY_COMMAND,
    environment: Mapping[str, str] | None = None,
) -> ApplyCompletion:
    """Pass one stable file unchanged to the public apply JSON command."""
    completed = subprocess.run(
        [*apply_command, "apply", "--json", os.fspath(path)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    apply_result, invalid_response_text = _parse_apply_response(completed.stdout)
    return ApplyCompletion(
        process_exit_code=completed.returncode,
        apply_result=apply_result,
        invalid_response_text=invalid_response_text,
        stderr_text=completed.stderr.decode("utf-8", errors="replace"),
    )
