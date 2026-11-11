"""Request-local deprecation delivery for the independent script runner."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TextIO
import warnings


_CLI_NOTICE_ACTIVE: ContextVar[bool] = ContextVar("script_cli_notice_active", default=False)


def warn_script_api() -> None:
    """Warn the library caller unless this CLI request already explained the move."""
    if not _CLI_NOTICE_ACTIVE.get():
        warnings.warn(
            "DEPRECATED: 'api.run_scripts' is deprecated. "
            "Use a Task Bundle with 'patchharbor execute' in a Git repository instead.",
            FutureWarning,
            stacklevel=3,
        )


@contextmanager
def script_cli_notice(stderr: TextIO) -> Iterator[None]:
    """Own one CLI warning without replacing process-wide warning filters/sinks."""
    print(
        "DEPRECATED: 'patchharbor fs run' is deprecated. "
        "Use a Task Bundle with 'patchharbor execute' in a Git repository instead.",
        file=stderr,
    )
    token = _CLI_NOTICE_ACTIVE.set(True)
    try:
        yield
    finally:
        _CLI_NOTICE_ACTIVE.reset(token)
