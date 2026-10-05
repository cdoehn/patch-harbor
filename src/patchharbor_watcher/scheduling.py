"""Monotone per-root work generations; no filesystem, threads or Core calls."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor_watcher.protocol import LockReference, Progress

QUIET_SECONDS = 5.0


@dataclass
class PendingRoot:
    target: object
    generation: int
    due: float
    dirty: bool = True
    lock: LockReference | None = None
    probe_at: float | None = None
    backoff: float = 5.0


class Schedule:
    def __init__(self):
        self.roots: dict[Path, PendingRoot] = {}
        self._generation = 0

    def replace(self, targets, now: float):
        # A fresh subscription always gets a full initial quiet period.
        self.roots = {}
        for target in targets:
            self._generation += 1
            self.roots[target.directory] = PendingRoot(target, self._generation, now + QUIET_SECONDS)

    def changed(self, directory: Path, now: float):
        root = self.roots.get(directory)
        if root is not None:
            self._generation += 1
            root.generation = self._generation
            root.due = now + QUIET_SECONDS
            root.dirty = True

    def ready(self, now: float):
        return tuple(root.target for _, root in sorted(self.roots.items(), key=lambda item: str(item[0]))
                     if root.dirty and root.lock is None and root.due <= now)

    def begin(self, targets):
        snapshot = {}
        for target in targets:
            root = self.roots[target.directory]
            snapshot[target.directory] = (target, root.generation)
            root.dirty = False
        return snapshot

    def finish(self, snapshot, progress: Progress, now: float):
        for directory, (target, generation) in snapshot.items():
            root = self.roots.get(directory)
            if root is None or root.target != target:
                continue
            if progress.status == 'locked':
                root.dirty = True
                root.lock = progress.blocked_on
                root.backoff = 5.0
                root.probe_at = now + root.backoff
            elif progress.status == 'attempted':
                # Core consumed one identity, possibly with a failed script.
                # Automatic replay rules decide whether any other work remains.
                root.dirty = True
            elif root.generation == generation:
                root.dirty = False

    def probes(self, now: float):
        return tuple(dict.fromkeys(root.lock for root in self.roots.values()
                                   if root.lock is not None and root.probe_at <= now))

    def probed(self, lock, blocked_on, now: float):
        for root in self.roots.values():
            if root.lock == lock:
                root.lock = blocked_on
                if blocked_on is None:
                    root.probe_at = None
                else:
                    root.backoff = min(300.0, root.backoff * 2)
                    root.probe_at = now + root.backoff

    def probe_failed(self, lock):
        for root in self.roots.values():
            if root.lock == lock:
                root.lock = None
                root.probe_at = None
                root.dirty = False

    def timeout(self, now: float):
        deadlines = [root.probe_at if root.lock is not None else root.due
                     for root in self.roots.values() if root.dirty]
        return max(0.0, min(deadlines) - now) if deadlines else None
