"""Small immutable data carriers shared by PatchHarbor's input pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputArtifact:
    """One locally readable artifact supplied by an input source."""

    path: Path
    display_name: str


@dataclass(frozen=True)
class BundleScript:
    """One script in its bundle order."""

    text: str
    suffix: str


@dataclass(frozen=True)
class PatchBundle:
    """An ordered, non-empty collection of PatchHarbor scripts."""

    scripts: tuple[BundleScript, ...]
