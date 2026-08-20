from __future__ import annotations

import signal

from patchharbor_watcher.lifecycle import (
    WatcherStopController,
    installed_stop_signals,
)


def test_signal_scope_requests_stop_and_restores_handlers() -> None:
    controller = WatcherStopController()
    previous = {
        watched_signal: signal.getsignal(watched_signal)
        for watched_signal in (signal.SIGINT, signal.SIGTERM)
    }

    with installed_stop_signals(controller):
        installed = signal.getsignal(signal.SIGTERM)
        assert callable(installed)
        installed(signal.SIGTERM, None)
        assert controller.stop_requested()
        assert controller.wait(0.0)
        assert not controller.was_interrupted()

    assert {
        watched_signal: signal.getsignal(watched_signal)
        for watched_signal in previous
    } == previous


def test_sigint_is_retained_as_interrupt_completion() -> None:
    controller = WatcherStopController()

    controller.request_stop(signal.SIGINT, None)

    assert controller.stop_requested()
    assert controller.was_interrupted()
