"""Small lifecycle contract shared by platform-specific process trees."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
import subprocess
import time
from types import TracebackType
from typing import BinaryIO, Self


GRACEFUL_STOP_SECONDS = 2.0
FORCE_STOP_SECONDS = 1.0
PROCESS_TREE_POLL_SECONDS = 0.05


class ProcessState(Enum):
    """Terminal-independent states of one process-tree run."""

    RUNNING = auto()
    EXITED = auto()
    TIMED_OUT = auto()
    INTERRUPTED = auto()


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Result of waiting for and cleaning up one owned process tree."""

    state: ProcessState
    return_code: int | None = None


class ProcessTree(ABC):
    """Own one root process and every descendant started below it."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._state = ProcessState.RUNNING
        self._tree_stopped = False
        self._closed = False

    @property
    def output_stream(self) -> BinaryIO:
        """Return the merged binary stream captured from the root process."""
        stream = self._process.stdout
        if stream is None:
            raise RuntimeError("script process output is not captured")
        return stream

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

    def run(self, *, timeout_seconds: float) -> ProcessResult:
        """Wait once, classify the result, and stop all remaining processes."""
        if self._closed:
            raise RuntimeError("process tree is closed")
        if self._state is not ProcessState.RUNNING:
            raise RuntimeError("process tree has already been run")

        return_code: int | None = None
        try:
            return_code = self._wait_root(timeout_seconds=timeout_seconds)
            self._state = ProcessState.EXITED
        except subprocess.TimeoutExpired:
            self._state = ProcessState.TIMED_OUT
        except KeyboardInterrupt:
            self._state = ProcessState.INTERRUPTED

        self._stop_remaining_processes(
            graceful=self._state in {
                ProcessState.TIMED_OUT,
                ProcessState.INTERRUPTED,
            }
        )
        return ProcessResult(self._state, return_code)

    def close(self) -> None:
        """Guarantee process-tree cleanup and release platform resources once."""
        if self._closed:
            return

        cleanup_error: OSError | None = None
        try:
            self._stop_remaining_processes(graceful=False)
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

    def _stop_remaining_processes(self, *, graceful: bool) -> None:
        if self._tree_stopped:
            return

        if graceful:
            self._request_stop()
            stopped = self._wait_for_tree_exit(
                timeout_seconds=GRACEFUL_STOP_SECONDS
            )
        else:
            stopped = not self._tree_has_processes()

        if not stopped:
            self._force_stop()
            stopped = self._wait_for_tree_exit(
                timeout_seconds=FORCE_STOP_SECONDS
            )
        if not stopped:
            raise OSError("script process tree did not terminate")

        self._reap_root()
        self._tree_stopped = True

    def _wait_for_tree_exit(self, *, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while self._tree_has_processes():
            if time.monotonic() >= deadline:
                return False
            time.sleep(PROCESS_TREE_POLL_SECONDS)
        return True

    def _reap_root(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            self._process.wait(timeout=FORCE_STOP_SECONDS)
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
