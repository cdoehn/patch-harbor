"""POSIX process-tree ownership for PatchHarbor."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess

from patchharbor.platform.lifecycle import ProcessTree


class PosixProcessTree(ProcessTree):
    """Own a process group created in a fresh POSIX session."""

    @classmethod
    def start(cls, command: list[str], *, cwd: Path) -> PosixProcessTree:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        return cls(process)

    def _tree_has_processes(self) -> bool:
        self._process.poll()
        try:
            os.killpg(self._process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _request_stop(self) -> None:
        if not self._tree_has_processes():
            return
        try:
            os.killpg(self._process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def _force_stop(self) -> None:
        if not self._tree_has_processes():
            return
        try:
            os.killpg(self._process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
