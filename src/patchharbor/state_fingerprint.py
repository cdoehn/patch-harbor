"""Pure byte framing for the ``patchharbor-state-v1`` fingerprint."""

from __future__ import annotations

import hashlib


FINGERPRINT_ALGORITHM = "patchharbor-state-v1"
_FINGERPRINT_HEADER = b"PATCHHARBOR_STATE_FINGERPRINT\0" + b"1\0"


def _framed_field(name: bytes, payload: bytes) -> bytes:
    return name + b"\0" + len(payload).to_bytes(8, "big") + payload


def encode_fingerprint_stream(
    *,
    staged_records: tuple[bytes, ...] = (),
    unstaged_records: tuple[bytes, ...] = (),
    untracked_records: tuple[bytes, ...] = (),
) -> bytes:
    """Encode already canonical state records in their fixed section order."""
    return b"".join(
        (
            _FINGERPRINT_HEADER,
            _framed_field(
                b"staged-count",
                len(staged_records).to_bytes(8, "big"),
            ),
            *staged_records,
            _framed_field(
                b"unstaged-count",
                len(unstaged_records).to_bytes(8, "big"),
            ),
            *unstaged_records,
            _framed_field(
                b"untracked-count",
                len(untracked_records).to_bytes(8, "big"),
            ),
            *untracked_records,
        )
    )


def state_fingerprint_digest(
    *,
    staged_records: tuple[bytes, ...] = (),
    unstaged_records: tuple[bytes, ...] = (),
    untracked_records: tuple[bytes, ...] = (),
) -> str:
    """Return the full SHA-256 digest of one canonical state stream."""
    stream = encode_fingerprint_stream(
        staged_records=staged_records,
        unstaged_records=unstaged_records,
        untracked_records=untracked_records,
    )
    return hashlib.sha256(stream).hexdigest()
