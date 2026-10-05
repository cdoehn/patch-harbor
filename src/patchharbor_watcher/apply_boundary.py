"""Private worker-process transport for the separate PatchHarbor Watcher."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import subprocess
import sys
from typing import NoReturn

from patchharbor_watcher.protocol import Progress, encode_scope, read_progress

DEFAULT_APPLY_COMMAND = (sys.executable, "-m", "patchharbor_watcher.worker")


@dataclass(frozen=True, slots=True)
class ApplyCompletion:
    """Opaque completion returned by the public Core apply boundary."""

    process_exit_code: int
    apply_result: dict[str, object] | None
    invalid_response_text: str | None
    stderr_text: str

    @property
    def progress(self) -> Progress:
        try:
            if self.apply_result is None:
                raise ValueError('worker returned no document')
            return read_progress(self.apply_result.get('watcher_progress'))
        except (ValueError, TypeError, AttributeError):
            return Progress('error')


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
    exchanges=None,
    apply_command: Sequence[str] = DEFAULT_APPLY_COMMAND,
    environment: Mapping[str, str] | None = None,
) -> ApplyCompletion:
    """Run one API worker with the existing process and signal boundary.

    No new session, process group, timeout, retry, or shell is introduced. The
    worker calls api.apply_next with an advisory scope over its private stdin
    protocol. No explicit candidate path, manual retry or CLI flags are sent.
    """
    arguments = list(apply_command)
    completed = subprocess.run(
        arguments,
        check=False,
        input=encode_scope(exchanges),
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
