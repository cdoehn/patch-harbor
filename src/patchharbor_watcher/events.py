"""Native directory-event contract; no bundle discovery, timer or Apply policy.

One reader may block in read(); another thread may wake or close the source.
Timeout/wake/closed reads return (). Native failures are structured exceptions,
never a silent polling fallback. Rebinding creates a fresh source/generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from pathlib import Path
import stat
from threading import Lock, RLock
from time import monotonic
from typing import Protocol


class EventKind(str, Enum):
    CHANGED = "changed"
    ROOT_INVALIDATED = "root_invalidated"
    OVERFLOW = "overflow"


class EventErrorKind(str, Enum):
    UNSUPPORTED = "unsupported"
    INVALID_TARGET = "invalid_target"
    INVALID_EVENT = "invalid_event"
    IO = "io"


class EventBackendError(RuntimeError):
    def __init__(self, kind: EventErrorKind, message: str, *, native_code: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.native_code = native_code


@dataclass(frozen=True, slots=True)
class DirectoryEvent:
    """A hint to revalidate, never a trusted candidate path or Apply permission.

directory=None on OVERFLOW invalidates knowledge of every subscribed root.
name is a direct entry only, or None for a change to the root itself.
"""
    kind: EventKind
    directory: Path | None
    name: str | None = None


class EventSource(Protocol):
    def read(self, timeout: float | None = None) -> tuple[DirectoryEvent, ...]: ...
    def wake(self) -> None: ...
    def close(self) -> None: ...


def deadline_for(timeout: float | None) -> float | None:
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("event timeout must be a number or None")
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("event timeout must be finite and nonnegative")
    return monotonic() + timeout


def remaining(deadline: float | None) -> float | None:
    return None if deadline is None else max(0.0, deadline - monotonic())


def directory_identity(path: Path) -> tuple[int, int, int]:
    try:
        before = path.lstat()
        physical = path.resolve(strict=True)
        after = path.lstat()
        first = (before.st_dev, before.st_ino, before.st_mode)
        if (physical != path or not stat.S_ISDIR(before.st_mode) or not before.st_ino
                or first != (after.st_dev, after.st_ino, after.st_mode)):
            raise EventBackendError(EventErrorKind.INVALID_TARGET, "unstable directory identity")
        return first
    except (OSError, ValueError, RuntimeError) as exc:
        if isinstance(exc, EventBackendError):
            raise
        raise EventBackendError(EventErrorKind.INVALID_TARGET, "cannot observe directory",
                                native_code=getattr(exc, "errno", None)) from exc


class WatchPlan:
    """Flat roots plus filtered ancestor watches for replacement/rename detection.

No enumeration: only the supplied paths and their ancestors are stat'ed. Parent
events unrelated to a subscribed path never escape the adapter. Watches are
fixed for the lifetime of a source; no descriptor-generation reuse occurs.
"""
    def __init__(self, directories: tuple[Path, ...]):
        if not isinstance(directories, tuple) or any(not isinstance(p, Path) for p in directories):
            raise TypeError("directories must be a tuple of Path objects")
        if any(not p.is_absolute() for p in directories):
            raise ValueError("watch directories must be absolute")
        self.roots = tuple(sorted(set(directories), key=str))
        self.identities = {root: directory_identity(root) for root in self.roots}
        self.guards: dict[Path, dict[str, set[Path]]] = {}
        for root in self.roots:
            child = root
            for parent in root.parents:
                self.guards.setdefault(parent, {}).setdefault(child.name, set()).add(root)
                child = parent
        self.directories = tuple(sorted(set(self.roots) | set(self.guards), key=str))
        self.observed = {path: directory_identity(path) for path in self.directories}

    def revalidate(self) -> None:
        for path, identity in self.observed.items():
            if directory_identity(path) != identity:
                raise EventBackendError(EventErrorKind.INVALID_TARGET, "directory changed while subscribing")

    def invalidated(self, directory: Path) -> tuple[DirectoryEvent, ...]:
        return tuple(DirectoryEvent(EventKind.ROOT_INVALIDATED, root)
                     for root in self.roots if root == directory or directory in root.parents)

    def route(self, directory: Path, name: str | None, *, membership: bool = False,
              child_directory_metadata: bool = False) -> tuple[DirectoryEvent, ...]:
        events = []
        if directory in self.identities and not child_directory_metadata:
            events.append(DirectoryEvent(EventKind.CHANGED, directory, name))
        for root in sorted(self.guards.get(directory, {}).get(name, ()), key=str):
            invalid = membership
            if not invalid:
                try:
                    invalid = directory_identity(root) != self.identities[root]
                except EventBackendError:
                    invalid = True
            if invalid:
                events.append(DirectoryEvent(EventKind.ROOT_INVALIDATED, root))
        return tuple(events)


class EventBatch:
    """Bound memory per read; excessive distinct hints become one global overflow."""
    LIMIT = 512

    def __init__(self):
        self._events: dict[DirectoryEvent, None] = {}
        self._overflow = False

    def add(self, events: tuple[DirectoryEvent, ...]) -> None:
        for event in events:
            if self._overflow:
                break
            self._events[event] = None
            if len(self._events) > self.LIMIT or event == DirectoryEvent(EventKind.OVERFLOW, None):
                self._overflow = True
                self._events = {DirectoryEvent(EventKind.OVERFLOW, None): None}

    def result(self) -> tuple[DirectoryEvent, ...]:
        return tuple(self._events)


class SourceLifecycle:
    """Shared lock ownership, without signal handlers or background threads."""
    def __init__(self):
        self._reader = Lock()
        self._state = RLock()
        self._closer = Lock()
        self._closing = False
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
