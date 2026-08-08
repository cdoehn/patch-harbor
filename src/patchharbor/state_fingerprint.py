"""Pure byte framing for the ``patchharbor-state-v1`` fingerprint."""

from __future__ import annotations

import hashlib


FINGERPRINT_ALGORITHM = "patchharbor-state-v1"
_FINGERPRINT_HEADER = b"PATCHHARBOR_STATE_FINGERPRINT\0" + b"1\0"


def _framed_field(name: bytes, payload: bytes) -> bytes:
    return name + b"\0" + len(payload).to_bytes(8, "big") + payload


def state_fingerprint_digest(
    *,
    staged_records: tuple[bytes, ...] = (),
    unstaged_records: tuple[bytes, ...] = (),
    untracked_records: tuple[bytes, ...] = (),
) -> str:
    """Return the full SHA-256 digest of one canonical state stream."""
    digest = hashlib.sha256()
    digest.update(_FINGERPRINT_HEADER)
    for count_name, records in (
        (b"staged-count", staged_records),
        (b"unstaged-count", unstaged_records),
        (b"untracked-count", untracked_records),
    ):
        digest.update(
            _framed_field(
                count_name,
                len(records).to_bytes(8, "big"),
            )
        )
        for record in records:
            digest.update(record)
    return digest.hexdigest()
