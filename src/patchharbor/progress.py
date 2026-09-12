"""Request-local facts; no terminal, I/O, mutation decisions or global handlers.

These internal records deliberately carry complete identifiers and data. The
CLI's observer owns text/shortening/verbosity. Public callers use the event
exports and explicit observer parameter of patchharbor.api.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from patchharbor.models import RepositoryContext


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    phase: str
    message: str
    level: str = "info"
    identifiers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackageFile:
    name: str
    size_bytes: int
    kind: str


@dataclass(frozen=True, slots=True)
class RequestStarted:
    source_name: str
    files: tuple[PackageFile, ...]
    script_total: int
    warnings: tuple[str, ...] = ()
    requested_repo_id: str | None = None


@dataclass(frozen=True, slots=True)
class RepositoryResolved:
    context: RepositoryContext


@dataclass(frozen=True, slots=True)
class ScriptPrepared:
    name: str
    index: int
    total: int
    messages: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...] = ()


ProgressEvent = ActivityEvent | RequestStarted | RepositoryResolved | ScriptPrepared
ActivityObserver = Callable[[ProgressEvent], None]
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


def emit(event: ProgressEvent) -> None:
    """Publish immutable observations without granting permission to act."""
    observer = _observer.get()
    if observer is not None:
        try:
            observer(event)
        except Exception:
            # Optional observers must not turn a proven recovery, move or
            # publication into a failed/partial operation. Required raw-log I/O
            # keeps its independent error handling. Never catch BaseException.
            pass


def activity(phase: str, message: str, level: str = "info", *,
             identifiers: tuple[str, ...] = ()) -> None:
    """Report a real operation; shortening belongs only to its UI consumer."""
    emit(ActivityEvent(phase, message, level, identifiers))
