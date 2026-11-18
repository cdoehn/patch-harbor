"""Explicit request-local override of bundle byte and item-count budgets.

No environment variable, package field or persistent setting grants this mode.
Structural validation and filesystem identity checks are independent of it.
"""
from contextlib import contextmanager
from contextvars import ContextVar


_FORCE = ContextVar('patchharbor_bundle_size_override', default=False)


@contextmanager
def bundle_size_scope(force: bool = False):
    """Always restore the calling context, including after an interrupted request."""
    if type(force) is not bool:
        raise TypeError('force must be boolean')
    token = _FORCE.set(force)
    try:
        yield
    finally:
        _FORCE.reset(token)


def exceeds_bundle_limit(actual: int, maximum: int) -> bool:
    return not _FORCE.get() and actual > maximum


def bundle_read_limit(maximum: int) -> int | None:
    """None means unbounded bytes, without inventing another finite ceiling."""
    return None if _FORCE.get() else maximum


def bundle_read_size(maximum: int) -> int:
    """Argument for file-like read; never request an enormous sentinel allocation."""
    return -1 if _FORCE.get() else maximum + 1


def read_bundle_file(path, *, max_bytes):
    """Preserve stable no-follow reads when the explicit byte cap is lifted."""
    from patchharbor.platform.filesystem import (
        read_stable_regular_file, read_stable_regular_file_bounded,
    )
    if _FORCE.get():
        return read_stable_regular_file(path)
    return read_stable_regular_file_bounded(path, max_bytes=max_bytes)
