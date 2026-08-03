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
    """One named script in its bundle order."""

    text: str
    display_name: str


@dataclass(frozen=True)
class BundlePayload:
    """One byte-exact file carried by a ZIP PatchBundle."""

    relative_path: str
    content: bytes


@dataclass(frozen=True)
class PatchBundle:
    """Ordered scripts plus files made available before execution."""

    scripts: tuple[BundleScript, ...]
    payloads: tuple[BundlePayload, ...] = ()
