"""Native event lifecycle around scoped Core automatic Apply."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import json
import time
from typing import TextIO
from queue import Empty, Queue
from threading import Thread

import patchharbor.api as api
from patchharbor_watcher.events import EventKind
from patchharbor_watcher.platform import open_event_source
from patchharbor_watcher.observation import Observation
from patchharbor_watcher.protocol import LockReference
from patchharbor_watcher.scheduling import QUIET_SECONDS, Schedule

from patchharbor_watcher.apply_boundary import ApplyCompletion


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
        completion.progress.status == 'attempted'
        and
        completion.process_exit_code == 0
        and isinstance(response, dict)
        and response.get("command") == "apply"
        and response.get("success") is True
        and response.get("process_exit_code") == 0
    ):
        return WatcherPollOutcome.APPLIED

    if completion.progress.status == 'no_candidate':
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
    quiet_seconds: float,
    stream: TextIO,
) -> None:
    stream.write(
        _canonical_json(
            {
                "event": event,
                "scope": "registered_repositories",
                "quiet_seconds": quiet_seconds,
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
    return publish_completion(event_state, completion, log_stream, error_stream)


def publish_completion(event_state, completion, log_stream, error_stream):
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


def _readiness(lock: LockReference):
    core_lock = api.ApplyLock(api.ApplyLockKind(lock.kind),
                             None if lock.repo_id is None else api.RepositoryId(lock.repo_id))
    blocked = api.apply_readiness(core_lock).blocked_on
    return None if blocked is None else LockReference(
        blocked.kind.value, None if blocked.repo_id is None else str(blocked.repo_id))


def run_repository_watcher(
    *, delegate, log_stream: TextIO, error_stream: TextIO,
    stop_requested=_never_stop, bind_wake=lambda callback: None,
    target_provider=api.watch_targets, control_provider=api.watch_control_paths,
    readiness=_readiness, source_factory=open_event_source, clock=time.monotonic,
    worker_factory=Thread,
) -> None:
    """Block on events/deadlines; keep receiving while one isolated Apply runs.

    The main thread alone owns subscriptions and generations. A single helper
    thread waits for the existing worker process and wakes this event loop on
    completion. Stop retains the existing policy: wait for an active Apply;
    process-group signals continue to reach the worker through the OS.
    """
    schedule, observation = Schedule(), Observation()
    event_state = SharedWatcherEventState()
    completed = Queue(maxsize=1)
    source, worker, snapshot = None, None, None
    control_lock, control_probe, control_backoff = None, None, 5.0

    def wake():
        if source is not None:
            source.wake()

    def refresh():
        nonlocal source, control_lock, control_probe, control_backoff
        directories, failure = observation.refresh(target_provider, control_provider)
        fresh = source_factory(directories)
        previous, source = source, fresh
        if previous is not None:
            previous.close()
        schedule.replace(observation.targets, clock())
        blocked = getattr(failure, 'lock', None)
        control_lock = None if blocked is None else LockReference(
            blocked.kind.value, None if blocked.repo_id is None else str(blocked.repo_id))
        control_backoff = 5.0
        control_probe = None if control_lock is None else clock() + control_backoff
        if failure is not None:
            error_stream.write(f'patchharbor-watcher: {failure}\n')
            error_stream.flush()

    def accept(events):
        if any(observation.needs_refresh(event) for event in events):
            refresh()
            return
        now = clock()
        for event in events:
            if event.kind is EventKind.CHANGED:
                schedule.changed(event.directory, now)

    def invoke(targets):
        try:
            result = delegate(exchanges=targets)
        except BaseException as exc:
            result = exc
        completed.put(result)
        wake()

    _write_lifecycle_record('watcher_started', QUIET_SECONDS, log_stream)
    try:
        refresh()
        bind_wake(wake)
        while not stop_requested():
            # Drain observations that preceded an expiring deadline before
            # granting any scope. Changes after launch still reach Core gates.
            while True:
                events = source.read(0)
                if not events or stop_requested():
                    break
                accept(events)
            if stop_requested():
                break
            if worker is not None:
                try:
                    result = completed.get_nowait()
                except Empty:
                    pass
                else:
                    worker.join()
                    worker = None
                    if isinstance(result, BaseException):
                        raise result
                    publish_completion(event_state, result, log_stream, error_stream)
                    schedule.finish(snapshot, result.progress, clock())
            if worker is None:
                if control_lock is not None and control_probe <= clock():
                    blocked = readiness(control_lock)
                    if blocked is None:
                        refresh()
                    else:
                        control_lock = blocked
                        control_backoff = min(300.0, control_backoff * 2)
                        control_probe = clock() + control_backoff
                for lock in schedule.probes(clock()):
                    try:
                        schedule.probed(lock, readiness(lock), clock())
                    except api.PatchHarborError as exc:
                        schedule.probe_failed(lock)
                        error_stream.write(f'patchharbor-watcher: {exc}\n')
                        error_stream.flush()
                targets = schedule.ready(clock())
                if targets and not stop_requested():
                    snapshot = schedule.begin(targets)
                    worker = worker_factory(target=invoke, args=(targets,), name='patchharbor-apply')
                    worker.start()
            if not stop_requested():
                timeout = None if worker is not None else schedule.timeout(clock())
                if worker is None and control_probe is not None:
                    control_timeout = max(0.0, control_probe - clock())
                    timeout = control_timeout if timeout is None else min(timeout, control_timeout)
                accept(source.read(timeout))
    finally:
        bind_wake(None)
        # Keep the wake target alive until the completion thread has returned.
        if worker is not None:
            worker.join()
        if source is not None:
            source.close()
        _write_lifecycle_record('watcher_stopped', QUIET_SECONDS, log_stream)
