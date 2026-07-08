from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable, TextIO


ANSI_RESET = "\033[0m"
ANSI_COLORS = {
    "green": "\033[32m",
    "purple": "\033[35m",
    "yellow": "\033[33m",
    "red": "\033[31m",
}


@dataclass(frozen=True)
class FooterItem:
    label: str
    text: str
    color: str = "purple"


def colors_enabled(stream: TextIO | None = None, *, env: dict[str, str] | None = None) -> bool:
    if env is None:
        env = os.environ
    if "NO_COLOR" in env:
        return False
    if env.get("FORCE_COLOR"):
        return True

    if stream is None:
        stream = sys.stdout
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def colorize(text: str, color: str, *, enabled: bool = True) -> str:
    if not enabled:
        return text
    prefix = ANSI_COLORS.get(color)
    if not prefix:
        return text
    return f"{prefix}{text}{ANSI_RESET}"


def render_footer(items: Iterable[FooterItem], *, width: int = 60, color: bool = False) -> str:
    safe_width = max(20, width)
    rule = "=" * safe_width
    lines = [rule]

    for item in items:
        label = colorize(item.label, item.color, enabled=color)
        lines.append(f"{label}: {item.text}")

    lines.append(rule)
    return "\n".join(lines)


def print_footer(items: Iterable[FooterItem], *, stream: TextIO | None = None, width: int = 60) -> None:
    if stream is None:
        stream = sys.stdout
    enabled = colors_enabled(stream)
    print(render_footer(items, width=width, color=enabled), file=stream)
