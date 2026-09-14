"""Thin polling lifecycle around PatchHarbor Core automatic apply."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import json
import time
from typing import TextIO

from patchharbor_watcher.apply_boundary import ApplyCompletion


_NO_MATCHING_PATCH_MESSAGE = (
    "no state-bound patch package matches a registered repository"
)


class WatcherPollOutcome(str, Enum):
    """One shared-Core polling outcome visible to the watcher lifecycle."""

    WAITING = "waiting"
    APPLIED = "applied"
    ERROR = "error"


@dataclass(slots=True)
class SharedWatcherEventState:
    """Suppress repeated identical idle or error records without owning state."""

    last_signature: tuple[object, ...] | None = None

    def should_publish(self, signature: tuple[object, ...]) -> bool:
        if signature == self.last_signature:
            return False
        self.last_signature = signature
        return True


def _never_stop() -> bool:
    return False


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _apply_error_document(
    completion: ApplyCompletion,
) -> dict[str, object] | None:
    response = completion.apply_result
    if not isinstance(response, dict):
        return None
    error = response.get("error")
    return error if isinstance(error, dict) else None


def _shared_poll_outcome(completion: ApplyCompletion) -> WatcherPollOutcome:
    response = completion.apply_result
    if (
        completion.process_exit_code == 0
        and isinstance(response, dict)
        and response.get("command") == "apply"
        and response.get("success") is True
        and response.get("process_exit_code") == 0
    ):
        return WatcherPollOutcome.APPLIED

    error = _apply_error_document(completion)
    if (
        isinstance(response, dict)
        and response.get("command") == "apply"
        and response.get("success") is False
        and error is not None
        and error.get("kind") == "patch_package_error"
        and error.get("message") == _NO_MATCHING_PATCH_MESSAGE
    ):
        return WatcherPollOutcome.WAITING
    return WatcherPollOutcome.ERROR


def _completion_signature(
    outcome: WatcherPollOutcome,
    completion: ApplyCompletion,
) -> tuple[object, ...]:
    error = _apply_error_document(completion)
    if outcome is WatcherPollOutcome.WAITING:
        return (
            outcome.value,
            None if error is None else error.get("kind"),
            None if error is None else error.get("message"),
        )
    if outcome is WatcherPollOutcome.ERROR:
        return (
            outcome.value,
            completion.process_exit_code,
            None if error is None else error.get("kind"),
            None if error is None else error.get("message"),
            completion.invalid_response_text,
            completion.stderr_text,
        )
    return (
        outcome.value,
        completion.process_exit_code,
        _canonical_json(completion.apply_result),
    )


def _write_operational_record(
    outcome: WatcherPollOutcome,
    completion: ApplyCompletion,
    stream: TextIO,
) -> None:
    record = {
        "event": (
            "waiting_for_exchange_patch"
            if outcome is WatcherPollOutcome.WAITING
            else "automatic_apply_completed"
            if outcome is WatcherPollOutcome.APPLIED
            else "automatic_apply_failed"
        ),
        "scope": "registered_repositories",
        "process_exit_code": completion.process_exit_code,
        "apply_response_is_json_object": completion.apply_result is not None,
        "apply_result": completion.apply_result,
        "invalid_apply_response": completion.invalid_response_text,
    }
    stream.write(_canonical_json(record))
    stream.write("\n")
    stream.flush()


def _write_lifecycle_record(
    event: str,
    poll_interval_seconds: float,
    stream: TextIO,
) -> None:
    stream.write(
        _canonical_json(
            {
                "event": event,
                "scope": "registered_repositories",
                "poll_interval_seconds": poll_interval_seconds,
            }
        )
    )
    stream.write("\n")
    stream.flush()


def poll_repositories_once(
    event_state: SharedWatcherEventState,
    *,
    delegate: Callable[[], ApplyCompletion],
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
) -> WatcherPollOutcome | None:
    """Ask Core once to refresh all local settings and apply one eligible package."""
    if stop_requested():
        return None
    completion = delegate()
    outcome = _shared_poll_outcome(completion)
    signature = _completion_signature(outcome, completion)
    if event_state.should_publish(signature):
        _write_operational_record(
            outcome,
            completion,
            log_stream,
        )
        if outcome is WatcherPollOutcome.ERROR:
            if completion.stderr_text:
                error_stream.write(completion.stderr_text)
                if not completion.stderr_text.endswith("\n"):
                    error_stream.write("\n")
            else:
                error = _apply_error_document(completion)
                message = (
                    error.get("message")
                    if error is not None
                    else completion.invalid_response_text
                )
                if isinstance(message, str) and message:
                    error_stream.write(f"patchharbor-watcher: {message}\n")
            error_stream.flush()
    return outcome


def run_repository_watcher(
    *,
    delegate: Callable[[], ApplyCompletion],
    poll_interval_seconds: float = 1.0,
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
    wait_between_polls: Callable[[float], object] = time.sleep,
) -> None:
    """Poll the public automatic-Apply boundary until a stop is requested."""
    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be greater than zero")
    event_state = SharedWatcherEventState()
    _write_lifecycle_record(
        "watcher_started",
        poll_interval_seconds,
        log_stream,
    )
    try:
        while not stop_requested():
            poll_repositories_once(
                event_state,
                delegate=delegate,
                log_stream=log_stream,
                error_stream=error_stream,
                stop_requested=stop_requested,
            )
            if stop_requested():
                break
            wait_between_polls(poll_interval_seconds)
    finally:
        _write_lifecycle_record(
            "watcher_stopped",
            poll_interval_seconds,
            log_stream,
        )
