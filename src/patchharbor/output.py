"""Bounded line capture for one script execution."""

from __future__ import annotations

from collections import deque


RETAINED_OUTPUT_LINES = 10
VISIBLE_OUTPUT_LINES = 5


class RollingLineBuffer:
    """Keep only the newest script-output lines."""

    def __init__(self) -> None:
        self._lines: deque[str] = deque(maxlen=RETAINED_OUTPUT_LINES)

    def append(self, line: str) -> None:
        """Append one complete or final unterminated output line."""
        self._lines.append(line)

    @property
    def retained_lines(self) -> tuple[str, ...]:
        """Return the at most ten lines retained in memory."""
        return tuple(self._lines)

    @property
    def visible_lines(self) -> tuple[str, ...]:
        """Return the last five lines for the current simple output."""
        return tuple(self._lines)[-VISIBLE_OUTPUT_LINES:]
