"""Request-local observation only; no UI, I/O, decisions or global handlers.

Core boundaries emit facts only after/before the corresponding real operation.
An observer cannot grant permission or change a safety decision. CLI commands
bind it for their lifetime; library callers are silent by default.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

ActivityObserver = Callable[[str, str, str], None]
_observer: ContextVar[ActivityObserver | None] = ContextVar(
    "patchharbor_activity_observer", default=None,
)


@contextmanager
def observe_activity(observer: ActivityObserver | None) -> Iterator[None]:
    """Bind an observer to this request, restoring even after an exception."""
    token = _observer.set(observer)
    try:
        yield
    finally:
        _observer.reset(token)


def activity(phase: str, message: str, level: str = "info") -> None:
    """Report a fact without allowing an optional observer to affect execution."""
    observer = _observer.get()
    if observer is not None:
        try:
            observer(phase, message, level)
        except Exception:
            # Diagnostics must not turn a proven recovery, move, or publication
            # into a partial operation. Required raw-log I/O keeps its own errors.
            pass
