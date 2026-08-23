from __future__ import annotations

import subprocess

import pytest

from patchharbor.platform import ProcessState
from patchharbor.platform import lifecycle
from patchharbor.platform.lifecycle import ProcessTree


class _FakeRootProcess:
    def __init__(
        self,
        *,
        returncode: int | None = None,
        wait_error: BaseException | None = None,
    ) -> None:
        self.pid = 123456
        self.returncode = returncode
        self.wait_error = wait_error
        self.kill_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        if self.wait_error is not None:
            error = self.wait_error
            self.wait_error = None
            raise error
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9


class _TestProcessTree(ProcessTree):
    def __init__(
        self,
        process: _FakeRootProcess,
        *,
        tree_alive: bool = True,
        graceful_stop_works: bool = True,
    ) -> None:
        super().__init__(process)  # type: ignore[arg-type]
        self.tree_alive = tree_alive
        self.graceful_stop_works = graceful_stop_works
        self.resources_closed = 0

    def _tree_has_processes(self) -> bool:
        return self.tree_alive

    def _request_stop(self) -> None:
        if self.graceful_stop_works:
            self.tree_alive = False
            if self._process.returncode is None:
                self._process.returncode = -15

    def _force_stop(self) -> None:
        self.tree_alive = False
        if self._process.returncode is None:
            self._process.returncode = -9

    def _close_platform_resources(self) -> None:
        self.resources_closed += 1


def test_completed_run_returns_exit_code_and_removes_descendants() -> None:
    process = _FakeRootProcess(returncode=7)
    tree = _TestProcessTree(process, tree_alive=True)

    with tree:
        result = tree.run(timeout_seconds=1.5)

    assert result.state is ProcessState.EXITED
    assert result.return_code == 7
    assert not tree.tree_alive
    assert tree.resources_closed == 1


def test_timeout_returns_one_terminal_state_and_stops_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "GRACEFUL_STOP_SECONDS", 0.0)
    process = _FakeRootProcess(
        wait_error=subprocess.TimeoutExpired(["interpreter"], 1.5)
    )
    tree = _TestProcessTree(
        process,
        tree_alive=True,
        graceful_stop_works=False,
    )

    with tree:
        result = tree.run(timeout_seconds=1.5)

    assert result.state is ProcessState.TIMED_OUT
    assert result.return_code is None
    assert not tree.tree_alive
    assert tree.resources_closed == 1


def test_keyboard_interrupt_returns_one_terminal_state_and_stops_tree() -> None:
    process = _FakeRootProcess(wait_error=KeyboardInterrupt())
    tree = _TestProcessTree(process, tree_alive=True)

    with tree:
        result = tree.run(timeout_seconds=10)

    assert result.state is ProcessState.INTERRUPTED
    assert result.return_code is None
    assert not tree.tree_alive
    assert tree.resources_closed == 1


def test_process_tree_can_only_be_run_once() -> None:
    process = _FakeRootProcess(returncode=0)
    tree = _TestProcessTree(process, tree_alive=False)

    with tree:
        result = tree.run(timeout_seconds=1)
        with pytest.raises(RuntimeError, match="already been run"):
            tree.run(timeout_seconds=1)

    assert result.state is ProcessState.EXITED
    assert tree.resources_closed == 1


def test_context_cleanup_stops_tree_when_waiting_raises() -> None:
    process = _FakeRootProcess(wait_error=OSError("wait failed"))
    tree = _TestProcessTree(process, tree_alive=True)

    with pytest.raises(OSError, match="wait failed"):
        with tree:
            tree.run(timeout_seconds=1)

    assert not tree.tree_alive
    assert tree.resources_closed == 1


def test_cleanup_error_does_not_hide_existing_body_error() -> None:
    process = _FakeRootProcess(returncode=0)

    class _FailingCloseTree(_TestProcessTree):
        def _close_platform_resources(self) -> None:
            raise OSError("close failed")

    tree = _FailingCloseTree(process, tree_alive=True)

    with pytest.raises(RuntimeError, match="body failed"):
        with tree:
            raise RuntimeError("body failed")


class _PollingProcess:
    def __init__(self, return_codes: list[int | None]) -> None:
        self.args = ["interpreter"]
        self._return_codes = iter(return_codes)
        self.wait_calls = 0

    def poll(self) -> int | None:
        return next(self._return_codes)

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        raise AssertionError("polling helper must not block in wait()")


def test_root_reaping_uses_polling_instead_of_a_blocking_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _PollingProcess([None, 0])
    tree = _TestProcessTree(  # type: ignore[arg-type]
        process,
        tree_alive=False,
    )
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)

    tree.close()

    assert process.wait_calls == 0
    assert tree.resources_closed == 1


def test_polling_wait_observes_process_exit_without_blocking_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _PollingProcess([None, None, 7])
    monkeypatch.setattr(lifecycle.time, "sleep", lambda seconds: None)

    result = lifecycle.poll_process_until_exit(
        process,  # type: ignore[arg-type]
        timeout_seconds=1,
    )

    assert result == 7
    assert process.wait_calls == 0


def test_polling_wait_raises_timeout_without_blocking_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _PollingProcess([None, None])
    times = iter((0.0, 0.0, 1.1))
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(lifecycle.time, "sleep", lambda seconds: None)

    with pytest.raises(subprocess.TimeoutExpired):
        lifecycle.poll_process_until_exit(
            process,  # type: ignore[arg-type]
            timeout_seconds=1,
        )

    assert process.wait_calls == 0


def test_tree_exit_poll_does_not_sleep_past_its_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeRootProcess(returncode=None)
    tree = _TestProcessTree(
        process,
        tree_alive=True,
        graceful_stop_works=False,
    )
    times = iter((0.0, 0.98, 1.0))
    sleeps: list[float] = []
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(lifecycle.time, "sleep", sleeps.append)

    assert tree._wait_for_tree_exit(timeout_seconds=1.0) is False
    assert sleeps
    assert all(
        0 < delay <= lifecycle.PROCESS_TREE_POLL_SECONDS
        for delay in sleeps
    )
    assert sum(sleeps) <= 1.0
