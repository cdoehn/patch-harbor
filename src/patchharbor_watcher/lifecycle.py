"""Signal-driven stop lifecycle for the separate PatchHarbor Watcher."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
import signal
from queue import Empty, SimpleQueue
from types import FrameType


@dataclass
class WatcherStopController:
    """Coordinate graceful watcher termination without core coupling."""

    _notifications: SimpleQueue[None] = field(default_factory=SimpleQueue)
    _requested: bool = field(default=False, init=False)
    _signal_number: int | None = field(default=None, init=False)
    _wake: Callable[[], None] | None = field(default=None, init=False)

    def request_stop(
        self,
        _signal_number: int | None = None,
        _frame: FrameType | None = None,
    ) -> None:
        if self._signal_number is None and _signal_number is not None:
            self._signal_number = _signal_number
        if self._requested:
            return
        self._requested = True
        # CPython SimpleQueue.put is reentrant even when a signal interrupts
        # get. Event.set can deadlock on the interrupted Event.wait lock.
        # https://docs.python.org/3.10/library/queue.html#queue.SimpleQueue.put
        self._notifications.put(None)
        if self._wake is not None:
            self._wake()

    def bind_wake(self, wake: Callable[[], None] | None) -> None:
        self._wake = wake
        if wake is not None and self.stop_requested():
            wake()

    def stop_requested(self) -> bool:
        return self._requested

    def wait(self, timeout_seconds: float) -> bool:
        if self._requested:
            return True
        try:
            self._notifications.get(timeout=max(0.0, timeout_seconds))
        except Empty:
            return self._requested
        # Leave a stop token for any other waiter already blocked in get.
        self._notifications.put(None)
        return self._requested

    def was_interrupted(self) -> bool:
        return self._signal_number == signal.SIGINT


@contextmanager
def installed_stop_signals(
    controller: WatcherStopController,
) -> Iterator[None]:
    """Install SIGINT/SIGTERM stop handlers and restore previous handlers."""
    watched_signals = (signal.SIGINT, signal.SIGTERM)
    previous_handlers: dict[signal.Signals, object] = {}
    try:
        for watched_signal in watched_signals:
            previous_handlers[watched_signal] = signal.getsignal(watched_signal)
            signal.signal(watched_signal, controller.request_stop)
        yield
    finally:
        for watched_signal, previous_handler in previous_handlers.items():
            signal.signal(watched_signal, previous_handler)
