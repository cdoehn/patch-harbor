from __future__ import annotations

import subprocess

import pytest

from patchharbor.platform import ProcessTreeTimeout
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
        self.wait_calls: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.wait_error is not None:
            raise self.wait_error
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
        tree_states: list[bool] | None = None,
        wait_results: list[bool] | None = None,
    ) -> None:
        super().__init__(process)  # type: ignore[arg-type]
        self.tree_states = list(tree_states or [False])
        self.wait_results = list(wait_results or [])
        self.events: list[str] = []

    def _tree_has_processes(self) -> bool:
        self.events.append("has")
        if len(self.tree_states) > 1:
            return self.tree_states.pop(0)
        return self.tree_states[0]

    def _request_stop(self) -> None:
        self.events.append("request")

    def _force_stop(self) -> None:
        self.events.append("force")

    def _wait_for_tree_exit(self, *, timeout_seconds: float) -> bool:
        self.events.append(f"wait:{timeout_seconds:g}")
        if self.wait_results:
            return self.wait_results.pop(0)
        return True

    def _close_platform_resources(self) -> None:
        self.events.append("close")


def test_wait_translates_subprocess_timeout_to_lifecycle_timeout() -> None:
    process = _FakeRootProcess(
        wait_error=subprocess.TimeoutExpired(["interpreter"], 1.5)
    )
    tree = _TestProcessTree(process)

    with pytest.raises(ProcessTreeTimeout):
        tree.wait(timeout_seconds=1.5)

    assert process.wait_calls == [1.5]


def test_graceful_stop_uses_force_after_two_second_grace_period() -> None:
    process = _FakeRootProcess(returncode=0)
    tree = _TestProcessTree(
        process,
        wait_results=[False, True],
    )

    tree.stop(graceful=True)

    assert tree.events == ["request", "wait:2", "force", "wait:1"]


def test_natural_exit_race_does_not_force_an_already_empty_tree() -> None:
    process = _FakeRootProcess(returncode=0)
    tree = _TestProcessTree(
        process,
        wait_results=[True],
    )

    tree.stop(graceful=True)

    assert tree.events == ["request", "wait:2"]


def test_context_cleanup_runs_once_when_body_raises() -> None:
    process = _FakeRootProcess(returncode=0)
    tree = _TestProcessTree(process)

    with pytest.raises(RuntimeError, match="body failed"):
        with tree:
            raise RuntimeError("body failed")

    assert tree.events == ["has", "close"]
    tree.close()
    assert tree.events == ["has", "close"]


def test_cleanup_error_does_not_hide_existing_body_error() -> None:
    process = _FakeRootProcess(returncode=0)

    class _FailingCloseTree(_TestProcessTree):
        def _close_platform_resources(self) -> None:
            raise OSError("close failed")

    tree = _FailingCloseTree(process)

    with pytest.raises(RuntimeError, match="body failed"):
        with tree:
            raise RuntimeError("body failed")


def test_close_releases_platform_resources_when_stop_check_fails() -> None:
    process = _FakeRootProcess(returncode=0)

    class _FailingStopTree(_TestProcessTree):
        def _tree_has_processes(self) -> bool:
            raise OSError("tree query failed")

    tree = _FailingStopTree(process)

    with pytest.raises(OSError, match="tree query failed"):
        tree.close()

    assert tree.events == ["close"]
    tree.close()
    assert tree.events == ["close"]
