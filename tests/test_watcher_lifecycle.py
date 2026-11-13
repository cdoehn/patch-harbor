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


def test_wait_without_stop_reports_timeout_and_does_not_request_stop():
    controller = WatcherStopController()
    assert not controller.wait(0.0)
    assert not controller.wait(-1.0)
    assert not controller.stop_requested()


def test_one_stop_releases_concurrent_and_future_waiters():
    from threading import Barrier, Thread
    controller = WatcherStopController()
    ready = Barrier(5)
    results = []
    errors = []
    def wait():
        try:
            ready.wait(timeout=10)
            results.append(controller.wait(10))
        except BaseException as exc:
            errors.append(exc)
    threads = [Thread(target=wait, daemon=True) for _ in range(4)]
    for thread in threads:
        thread.start()
    try:
        ready.wait(timeout=10)
    finally:
        controller.request_stop()
        for thread in threads:
            thread.join(timeout=10)
    assert not errors and all(not thread.is_alive() for thread in threads)
    assert results == [True] * 4
    assert controller.wait(0.0)
