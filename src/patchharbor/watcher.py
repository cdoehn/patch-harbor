"""Thin polling watcher that delegates stable files to PatchHarbor Core."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from typing import NoReturn, TextIO


_BROWSER_TEMP_SUFFIXES = (
    ".crdownload",
    ".download",
    ".opdownload",
    ".part",
    ".partial",
    ".tmp",
)
_DEFAULT_APPLY_COMMAND = ("patchharbor",)


def _reject_nonfinite_json(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON value: {value}")


@dataclass(frozen=True)
class FileObservation:
    """One top-level regular file observation used for stability checks."""

    path: Path
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class ApplyCompletion:
    """Observed completion of one delegated public apply subprocess."""

    process_exit_code: int
    apply_result: dict[str, object] | None
    response_is_json_object: bool
    stderr_text: str


@dataclass
class WatcherState:
    """In-memory observations for one watcher process."""

    previous: dict[Path, FileObservation] = field(default_factory=dict)
    processed: dict[Path, FileObservation] = field(default_factory=dict)

    def observe(
        self,
        current: Sequence[FileObservation],
    ) -> tuple[FileObservation, ...]:
        """Return files unchanged across two consecutive observations."""
        current_by_path = {observation.path: observation for observation in current}
        stable = tuple(
            observation
            for observation in current
            if self.previous.get(observation.path) == observation
            and self.processed.get(observation.path) != observation
        )
        self.previous = current_by_path
        self.processed = {
            path: observation
            for path, observation in self.processed.items()
            if path in current_by_path
        }
        return stable

    def mark_processed(self, observation: FileObservation) -> None:
        """Avoid repeating one unchanged file during this watcher process."""
        self.processed[observation.path] = observation


def is_browser_temporary_name(name: str) -> bool:
    """Recognize common browser download-temporary suffixes."""
    lowered = name.casefold()
    return lowered.endswith(_BROWSER_TEMP_SUFFIXES)


def observe_input_directory(directory: Path) -> tuple[FileObservation, ...]:
    """Observe top-level regular non-temporary files without recursion."""
    observations: list[FileObservation] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if is_browser_temporary_name(entry.name):
                continue
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(metadata.st_mode):
                continue
            observations.append(
                FileObservation(
                    path=directory / entry.name,
                    size=metadata.st_size,
                    mtime_ns=metadata.st_mtime_ns,
                )
            )
    observations.sort(key=lambda item: os.fsencode(item.path.name))
    return tuple(observations)


def delegate_to_apply(
    path: Path,
    *,
    apply_command: Sequence[str] = _DEFAULT_APPLY_COMMAND,
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

    parsed: dict[str, object] | None = None
    response_is_json_object = False
    try:
        candidate = json.loads(
            completed.stdout.decode("utf-8"),
            parse_constant=_reject_nonfinite_json,
        )
    except (UnicodeDecodeError, ValueError):
        candidate = None
    if isinstance(candidate, dict):
        parsed = candidate
        response_is_json_object = True

    return ApplyCompletion(
        process_exit_code=completed.returncode,
        apply_result=parsed,
        response_is_json_object=response_is_json_object,
        stderr_text=completed.stderr.decode("utf-8", errors="replace"),
    )


def _write_operational_record(
    observation: FileObservation,
    completion: ApplyCompletion,
    stream: TextIO,
) -> None:
    record = {
        "event": "apply_completed",
        "input_path": os.fspath(observation.path),
        "process_exit_code": completion.process_exit_code,
        "apply_response_is_json_object": completion.response_is_json_object,
        "apply_result": completion.apply_result,
    }
    stream.write(
        json.dumps(
            record,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    stream.write("\n")
    stream.flush()


def poll_input_directory_once(
    directory: Path,
    state: WatcherState,
    *,
    apply_command: Sequence[str] = _DEFAULT_APPLY_COMMAND,
    environment: Mapping[str, str] | None = None,
    log_stream: TextIO,
    error_stream: TextIO,
    delegate: Callable[[Path], ApplyCompletion] | None = None,
) -> int:
    """Observe once and delegate every newly stable top-level file."""
    stable = state.observe(observe_input_directory(directory))
    delegated = 0
    for observation in stable:
        completion = (
            delegate(observation.path)
            if delegate is not None
            else delegate_to_apply(
                observation.path,
                apply_command=apply_command,
                environment=environment,
            )
        )
        _write_operational_record(observation, completion, log_stream)
        if completion.stderr_text:
            error_stream.write(completion.stderr_text)
            if not completion.stderr_text.endswith("\n"):
                error_stream.write("\n")
            error_stream.flush()
        state.mark_processed(observation)
        delegated += 1
    return delegated


def _never_stop() -> bool:
    return False


def run_watcher(
    input_directory: Path,
    *,
    poll_interval_seconds: float = 1.0,
    apply_command: Sequence[str] = _DEFAULT_APPLY_COMMAND,
    environment: Mapping[str, str] | None = None,
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Periodically scan one non-recursive input directory until stopped."""
    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be greater than zero")
    directory = input_directory.expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise NotADirectoryError(os.fspath(directory))

    state = WatcherState()
    while not stop_requested():
        poll_input_directory_once(
            directory,
            state,
            apply_command=apply_command,
            environment=environment,
            log_stream=log_stream,
            error_stream=error_stream,
        )
        if stop_requested():
            break
        sleeper(poll_interval_seconds)
