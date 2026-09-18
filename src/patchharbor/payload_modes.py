"""Permission policy for repository payloads, not private application state."""
from __future__ import annotations

DEFAULT_PAYLOAD_MODE = 0o644
FORBIDDEN_EXISTING_BITS = 0o7000  # setuid, setgid and sticky
FORBIDDEN_PAYLOAD_BITS = FORBIDDEN_EXISTING_BITS | 0o022


def validate_existing_payload_mode(mode: int) -> int:
    """Preserve local rwx policy, including shared writes; reject special bits.

    This is not permission to request those bits in a ZIP. It accepts only an
    observed existing regular target's mode, never a new file's requested mode.
    """
    if type(mode) is not int or not 0 <= mode <= 0o7777:
        raise ValueError("payload mode must contain only POSIX permission bits")
    if mode & FORBIDDEN_EXISTING_BITS:
        raise ValueError(f"unsafe existing payload permissions: {mode:04o}")
    return mode


def validate_payload_mode(mode: int) -> int:
    """Validate requested ZIP/API permissions; never grant shared write bits."""
    validate_existing_payload_mode(mode)
    if mode & FORBIDDEN_PAYLOAD_BITS:
        raise ValueError(f"unsafe payload permissions: {mode:04o}")
    return mode


def select_payload_mode(requested: int | None, existing: int | None) -> int:
    """Validate the strict request, then preserve an existing ordinary rwx mode.

    An unsafe request stays invalid even if an existing target would override it.
    Existing group/other-write bits are local policy, not a new ZIP grant.
    """
    bundled = DEFAULT_PAYLOAD_MODE if requested is None else validate_payload_mode(requested)
    return bundled if existing is None else validate_existing_payload_mode(existing)
