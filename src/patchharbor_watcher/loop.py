"""Native event lifecycle around scoped Core automatic Execute."""

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
from patchharbor_watcher.observation import Observation, live_observation
from patchharbor_watcher.protocol import LockReference
from patchharbor_watcher.scheduling import QUIET_SECONDS, Schedule

from patchharbor_watcher.execute_boundary import ExecuteCompletion


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


def _execute_error_document(
    completion: ExecuteCompletion,
) -> dict[str, object] | None:
    response = completion.execute_result
    if not isinstance(response, dict):
        return None
    error = response.get("error")
    return error if isinstance(error, dict) else None


def _shared_poll_outcome(completion: ExecuteCompletion) -> WatcherPollOutcome:
    response = completion.execute_result
    if (
        completion.progress.status == 'attempted'
        and
        completion.process_exit_code == 0
        and isinstance(response, dict)
        and response.get("command") == "execute"
        and response.get("success") is True
        and response.get("process_exit_code") == 0
    ):
        return WatcherPollOutcome.APPLIED

    if completion.progress.status == 'no_candidate':
        return WatcherPollOutcome.WAITING
    return WatcherPollOutcome.ERROR


def _completion_signature(
    outcome: WatcherPollOutcome,
    completion: ExecuteCompletion,
) -> tuple[object, ...]:
    error = _execute_error_document(completion)
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
        _canonical_json(completion.execute_result),
    )


def _write_operational_record(
    outcome: WatcherPollOutcome,
    completion: ExecuteCompletion,
    stream: TextIO,
) -> None:
    record = {
        "event": (
            "waiting_for_exchange_patch"
            if outcome is WatcherPollOutcome.WAITING
            else "automatic_execute_completed"
            if outcome is WatcherPollOutcome.APPLIED
            else "automatic_execute_failed"
        ),
        "scope": "registered_repositories",
        "process_exit_code": completion.process_exit_code,
        "execute_response_is_json_object": completion.execute_result is not None,
        "execute_result": completion.execute_result,
        "invalid_execute_response": completion.invalid_response_text,
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
    delegate: Callable[[], ExecuteCompletion],
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
) -> WatcherPollOutcome | None:
    """Ask Core once to refresh all local settings and execute one eligible package."""
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
                error = _execute_error_document(completion)
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
    core_lock = api.ExecuteLock(api.ExecuteLockKind(lock.kind),
                             None if lock.repo_id is None else api.RepositoryId(lock.repo_id))
    blocked = api.execute_readiness(core_lock).blocked_on
    return None if blocked is None else LockReference(
        blocked.kind.value, None if blocked.repo_id is None else str(blocked.repo_id))


def run_repository_watcher(
    *, delegate, log_stream: TextIO, error_stream: TextIO,
    stop_requested=_never_stop, bind_wake=lambda callback: None,
    target_provider=api.watch_targets, control_provider=api.watch_control_paths,
    readiness=_readiness, source_factory=open_event_source, clock=time.monotonic,
    worker_factory=Thread, publication_factory=api.watcher_observation,
) -> None:
    """Block on events/deadlines; keep receiving while one isolated Execute runs.

    The main thread alone owns subscriptions and generations. A single helper
    thread waits for the existing worker process and wakes this event loop on
    completion. Stop retains the existing policy: wait for an active Execute;
    process-group signals continue to reach the worker through the OS.
    """
    schedule, observation = Schedule(), Observation()
    event_state = SharedWatcherEventState()
    completed = Queue(maxsize=1)
    source, worker, snapshot = None, None, None
    control_lock, control_probe, control_backoff = None, None, 5.0
    publication = publication_factory()
    subscribed = ()

    def publish_status():
        publication.update(**live_observation(schedule, subscribed, applying=worker is not None,
            control_lock=control_lock, control_probe=control_probe, now=clock(), wall=time.time(),
            active_exchanges=tuple(snapshot or ()) if worker is not None else ()))

    def wake():
        if source is not None:
            source.wake()

    def refresh():
        nonlocal source, control_lock, control_probe, control_backoff, subscribed
        publication.update(activity_code='refreshing')
        directories, failure = observation.refresh(target_provider, control_provider)
        publication.update(activity_code='subscribing')
        fresh = source_factory(directories)
        subscribed = directories
        previous, source = source, fresh
        if previous is not None:
            previous.close()
        schedule.replace(observation.targets, clock())
        blocked = getattr(failure, 'lock', None)
        control_lock = None if blocked is None else LockReference(
            blocked.kind.value, None if blocked.repo_id is None else str(blocked.repo_id))
        control_backoff = 5.0
        control_probe = None if control_lock is None else clock() + control_backoff
        publication.update(last_error=str(failure) if failure is not None else None)
        if failure is not None:
            publication.update(activity_code='configuration-error', activity_status='failure')
        publish_status()
        if failure is not None:
            error_stream.write(f'patchharbor-watcher: {failure}\n')
            error_stream.flush()

    def accept(events):
        if any(observation.needs_refresh(event) for event in events):
            publication.update(activity_code='overflow' if any(e.kind is EventKind.OVERFLOW for e in events)
                               else 'replaced', activity_status='unknown')
            refresh()
            return
        now = clock()
        for event in events:
            if event.kind is EventKind.CHANGED:
                schedule.changed(event.directory, now)
                publication.update(activity_code='changed', activity_status='success',
                                   activity_message='Änderung erkannt · ' + str(event.directory))

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
                    publication.update(activity_code='completion')
                    if isinstance(result, BaseException):
                        raise result
                    progress = result.progress
                    if progress.status == 'attempted':
                        publication.update(activity_code='execute-completed',
                                           activity_status='success' if result.process_exit_code == 0 else 'failure',
                                           activity_message='Execute abgeschlossen · Exit ' + str(result.process_exit_code))
                    code = ('no-candidate' if progress.status == 'no_candidate' else
                            'pending' if progress.status == 'attempted' else
                            progress.blocked_on.kind + '-lock' if progress.status == 'locked' else 'waiting-change')
                    publication.update(activity_code=code, activity_status='waiting')
                    publish_completion(event_state, result, log_stream, error_stream)
                    schedule.finish(snapshot, result.progress, clock())
            if worker is None:
                if control_lock is not None and control_probe <= clock():
                    publication.update(activity_code='lock-probe')
                    blocked = readiness(control_lock)
                    publication.update(activity_code='lock-free' if blocked is None else 'lock-held',
                                       activity_status='success' if blocked is None else 'waiting')
                    if blocked is None:
                        refresh()
                    else:
                        control_lock = blocked
                        control_backoff = min(300.0, control_backoff * 2)
                        control_probe = clock() + control_backoff
                for lock in schedule.probes(clock()):
                    try:
                        publication.update(activity_code='lock-probe')
                        blocked = readiness(lock)
                        publication.update(activity_code='lock-free' if blocked is None else 'lock-held',
                                           activity_status='success' if blocked is None else 'waiting')
                        schedule.probed(lock, blocked, clock())
                    except api.PatchHarborError as exc:
                        publication.update(activity_code='probe-failed', activity_status='failure', last_error=str(exc)[:1024])
                        schedule.probe_failed(lock)
                        error_stream.write(f'patchharbor-watcher: {exc}\n')
                        error_stream.flush()
                targets = schedule.ready(clock())
                if targets and not stop_requested():
                    snapshot = schedule.begin(targets)
                    publication.update(activity_code='worker-start')
                    worker = worker_factory(target=invoke, args=(targets,), name='patchharbor-execute')
                    worker.start()
            publish_status()
            if not stop_requested():
                timeout = None if worker is not None else schedule.timeout(clock())
                if worker is None and control_probe is not None:
                    control_timeout = max(0.0, control_probe - clock())
                    timeout = control_timeout if timeout is None else min(timeout, control_timeout)
                accept(source.read(timeout))
    except BaseException as exc:
        publication.update(last_error=str(exc)[:1024] or type(exc).__name__,
                           activity_code='watcher-error', activity_status='failure')
        raise
    finally:
        bind_wake(None)
        publication.update(activity_code='stopping', activity_status='waiting')
        # Keep the wake target alive until the completion thread has returned.
        if worker is not None:
            publication.update(activity_code='draining', activity_status='waiting')
            worker.join()
        if source is not None:
            source.close()
        publication.update(phase='stopped')
        publication.close()
        _write_lifecycle_record('watcher_stopped', QUIET_SECONDS, log_stream)
