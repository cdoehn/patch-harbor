from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor_watcher.apply_boundary import ApplyCompletion
from patchharbor_watcher.loop import (
    SharedWatcherEventState,
    WatcherPollOutcome,
    poll_repositories_once,
    run_repository_watcher,
)


def _completion(
    *,
    exit_code: int = 0,
    result: dict[str, object] | None = None,
    invalid_response: str | None = None,
    stderr: str = "",
) -> ApplyCompletion:
    return ApplyCompletion(
        process_exit_code=exit_code,
        apply_result={"success": True} if result is None else result,
        invalid_response_text=invalid_response,
        stderr_text=stderr,
    )


def _automatic_apply_envelope(
    *,
    success: bool,
    process_exit_code: int,
    error_kind: str | None = None,
    error_message: str | None = None,
    run_id: str = "run-id",
) -> dict[str, object]:
    return {
        "watcher_progress": {"version": 1, "status": "no_candidate" if run_id.startswith("idle-") else "attempted" if success else "error", "blocked_on": None},
        "output_version": 1,
        "command": "apply",
        "success": success,
        "result": {
            "run_id": run_id,
            "repository_resolved": success,
        },
        "error": (
            None
            if error_kind is None
            else {
                "kind": error_kind,
                "message": error_message,
            }
        ),
        "process_exit_code": process_exit_code,
    }


def test_shared_poll_delegates_to_core_and_deduplicates_idle_records(
    tmp_path: Path,
) -> None:
    exchange = tmp_path.resolve()
    calls = 0
    run_ids = iter(("idle-one", "idle-two"))
    log = StringIO()
    errors = StringIO()

    def delegate() -> ApplyCompletion:
        nonlocal calls
        calls += 1
        return _completion(
            exit_code=10,
            result=_automatic_apply_envelope(
                success=False,
                process_exit_code=10,
                error_kind="patch_package_error",
                error_message=(
                    "no state-bound patch package matches a registered repository"
                ),
                run_id=next(run_ids),
            ),
        )

    state = SharedWatcherEventState()
    first = poll_repositories_once(
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )
    second = poll_repositories_once(
        state,
        delegate=delegate,
        log_stream=log,
        error_stream=errors,
    )

    assert (first, second) == (
        WatcherPollOutcome.WAITING,
        WatcherPollOutcome.WAITING,
    )
    assert calls == 2
    records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "waiting_for_exchange_patch"
    assert records[0]["scope"] == "registered_repositories"
    assert "input_path" not in records[0]
    assert errors.getvalue() == ""


def test_shared_poll_records_success_and_distinct_core_error(
    tmp_path: Path,
) -> None:
    exchange = tmp_path.resolve()
    completions = iter(
        (
            _completion(
                result=_automatic_apply_envelope(
                    success=True,
                    process_exit_code=0,
                    run_id="applied-run",
                )
            ),
            _completion(
                exit_code=10,
                result=_automatic_apply_envelope(
                    success=False,
                    process_exit_code=10,
                    error_kind="patch_package_error",
                    error_message=(
                        "selected exchange patch changed during automatic discovery"
                    ),
                    run_id="changed-run",
                ),
                stderr="core diagnostic",
            ),
        )
    )
    log = StringIO()
    errors = StringIO()
    state = SharedWatcherEventState()

    outcomes = tuple(
        poll_repositories_once(
            state,
            delegate=lambda: next(completions),
            log_stream=log,
            error_stream=errors,
        )
        for _ in range(2)
    )

    assert outcomes == (
        WatcherPollOutcome.APPLIED,
        WatcherPollOutcome.ERROR,
    )
    records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert [record["event"] for record in records] == [
        "automatic_apply_completed",
        "automatic_apply_failed",
    ]
    assert errors.getvalue() == "core diagnostic\n"


def test_repeated_identical_core_error_is_logged_once(
    tmp_path: Path,
) -> None:
    completion = _completion(
        exit_code=4,
        result=_automatic_apply_envelope(
            success=False,
            process_exit_code=4,
            error_kind="configuration_error",
            error_message="configuration changed",
        ),
        stderr="configuration changed",
    )
    log = StringIO()
    errors = StringIO()
    state = SharedWatcherEventState()

    for _ in range(3):
        assert poll_repositories_once(
            state,
            delegate=lambda: completion,
            log_stream=log,
            error_stream=errors,
        ) is WatcherPollOutcome.ERROR

    assert len(log.getvalue().splitlines()) == 1
    assert errors.getvalue() == "configuration changed\n"
