"""Small immutable data carriers shared by PatchHarbor's input pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patchharbor.parser import ParsedScript


@dataclass(frozen=True)
class InputArtifact:
    """One locally readable artifact supplied by an input source."""

    path: Path
    display_name: str
    remove_after_use: bool


@dataclass(frozen=True)
class BundleScript:
    """One parsed script in its bundle order."""

    script: ParsedScript
    suffix: str
    display_name: str


@dataclass(frozen=True)
class PatchBundle:
    """An ordered, non-empty collection of PatchHarbor scripts."""

    scripts: tuple[BundleScript, ...]
