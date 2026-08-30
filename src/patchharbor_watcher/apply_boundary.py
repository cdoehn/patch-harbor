"""Public subprocess boundary used by the separate PatchHarbor Watcher."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import subprocess
import sys
from typing import NoReturn


DEFAULT_APPLY_COMMAND = (sys.executable, "-m", "patchharbor.cli")


@dataclass(frozen=True, slots=True)
class ApplyCompletion:
    """Opaque completion returned by the public Core apply boundary."""

    process_exit_code: int
    apply_result: dict[str, object] | None
    invalid_response_text: str | None
    stderr_text: str


def _reject_nonfinite_json(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON value: {value}")


def _parse_apply_response(
    stdout: bytes,
) -> tuple[dict[str, object] | None, str | None]:
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


def delegate_to_automatic_apply(
    *,
    apply_command: Sequence[str] = DEFAULT_APPLY_COMMAND,
    environment: Mapping[str, str] | None = None,
) -> ApplyCompletion:
    """Ask Core to discover and process one shared Exchange candidate."""
    arguments = [*apply_command, "apply", "--json", "--automatic"]
    completed = subprocess.run(
        arguments,
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
