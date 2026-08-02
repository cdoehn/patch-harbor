"""Small lifecycle contract shared by platform-specific process trees."""

from __future__ import annotations

from abc import ABC, abstractmethod
import subprocess
import time
from types import TracebackType
from typing import Self


FORCE_KILL_GRACE_SECONDS = 2.0
_FORCE_KILL_WAIT_SECONDS = 1.0
_PROCESS_TREE_POLL_SECONDS = 0.05


class ProcessTreeTimeout(TimeoutError):
    """The root process exceeded its configured execution timeout."""


class ProcessTree(ABC):
    """Own one root process and every descendant started below it."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        try:
            self.close()
        except OSError:
            if exc_type is None:
                raise
        return False

    def wait(self, *, timeout_seconds: float) -> int:
        """Wait for the root process while preserving platform interrupt behavior."""
        try:
            return self._wait_root(timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise ProcessTreeTimeout from exc

    def stop(self, *, graceful: bool) -> None:
        """Stop all remaining processes and reap the root process."""
        if self._closed:
            return

        if graceful:
            self._request_stop()
            stopped = self._wait_for_tree_exit(
                timeout_seconds=FORCE_KILL_GRACE_SECONDS
            )
        else:
            stopped = not self._tree_has_processes()

        if not stopped:
            self._force_stop()
            stopped = self._wait_for_tree_exit(
                timeout_seconds=_FORCE_KILL_WAIT_SECONDS
            )
        if not stopped:
            raise OSError("script process tree did not terminate")

        self._reap_root()

    def close(self) -> None:
        """Guarantee process-tree cleanup and release platform resources once."""
        if self._closed:
            return

        cleanup_error: OSError | None = None
        try:
            self.stop(graceful=False)
        except OSError as exc:
            cleanup_error = exc
        try:
            self._close_platform_resources()
        except OSError as exc:
            if cleanup_error is None:
                cleanup_error = exc
        self._closed = True

        if cleanup_error is not None:
            raise cleanup_error

    def _wait_for_tree_exit(self, *, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while self._tree_has_processes():
            if time.monotonic() >= deadline:
                return False
            time.sleep(_PROCESS_TREE_POLL_SECONDS)
        return True

    def _reap_root(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            self._process.wait(timeout=_FORCE_KILL_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

    def _wait_root(self, *, timeout_seconds: float) -> int:
        return self._process.wait(timeout=timeout_seconds)

    @abstractmethod
    def _tree_has_processes(self) -> bool:
        """Return whether the owned process tree still contains processes."""

    @abstractmethod
    def _request_stop(self) -> None:
        """Request a graceful stop of the owned process tree."""

    @abstractmethod
    def _force_stop(self) -> None:
        """Force the owned process tree to terminate."""

    def _close_platform_resources(self) -> None:
        """Release resources that are not owned by subprocess.Popen."""
