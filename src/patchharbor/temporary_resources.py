"""Private per-request temporary resources shared by runner workflows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile


def system_temporary_directory() -> Path:
    """Return the physically resolved system temporary directory."""
    return Path(tempfile.gettempdir()).resolve(strict=True)


def create_private_request_directory(
    *,
    prefix: str | None = None,
    name: str | None = None,
) -> Path:
    """Create one user-private request directory below the system temp root."""
    if (prefix is None) == (name is None):
        raise ValueError("exactly one temporary directory prefix or name is required")

    root = system_temporary_directory()
    if name is not None:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("temporary request directory name must be simple")
        path = root / name
        path.mkdir(mode=0o700)
    else:
        path = Path(tempfile.mkdtemp(prefix=prefix, dir=root))

    return path.resolve(strict=True)


def remove_private_request_directory(path: Path) -> None:
    """Best-effort remove one complete private request directory."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError:
        # Cleanup must not replace the primary request result.
        pass


@contextmanager
def private_request_directory(*, prefix: str) -> Iterator[Path]:
    """Own one temporary request directory and remove it on every exit path."""
    path = create_private_request_directory(prefix=prefix)
    try:
        yield path
    finally:
        remove_private_request_directory(path)


def create_private_file(path: Path, *, mode: int = 0o600) -> int:
    """Exclusively create one private file and return its descriptor."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    return os.open(path, flags, mode)


def write_private_bytes(path: Path, content: bytes) -> None:
    """Exclusively write one byte-exact private file."""
    descriptor: int | None = create_private_file(path)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
    finally:
        if descriptor is not None:
            os.close(descriptor)
