"""Signal-driven stop lifecycle for the separate PatchHarbor Watcher."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import signal
from threading import Event
from types import FrameType


@dataclass
class WatcherStopController:
    """Coordinate graceful watcher termination without core coupling."""

    _event: Event = field(default_factory=Event)
    _signal_number: int | None = field(default=None, init=False)

    def request_stop(
        self,
        _signal_number: int | None = None,
        _frame: FrameType | None = None,
    ) -> None:
        if self._signal_number is None and _signal_number is not None:
            self._signal_number = _signal_number
        self._event.set()

    def stop_requested(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout_seconds: float) -> bool:
        return self._event.wait(timeout_seconds)

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
