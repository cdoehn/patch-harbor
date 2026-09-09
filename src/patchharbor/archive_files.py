"""Collision-safe file relocation, separate from archival eligibility proofs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from patchharbor.exchange_state import ExchangeFileIdentity
from patchharbor.platform.archive import ArchiveLocation, move_archive_file


def archive_verified_file(
    location: ArchiveLocation, identity: ExchangeFileIdentity,
    *, verify_eligibility: Callable[[], None],
) -> Path:
    """Retain the original filename normally; never replace on name collisions."""
    name = identity.path.name
    for attempt in range(5):
        candidate = name if attempt == 0 else f"{name}.archive-{uuid4().hex}"
        try:
            return move_archive_file(location, identity.path, target_name=candidate,
                                     expected_sha256=identity.sha256, verify_eligibility=verify_eligibility)
        except FileExistsError:
            continue
    raise FileExistsError("could not reserve a collision-free archive filename")
