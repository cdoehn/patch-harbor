"""Portable, byte-preserving repository-relative path boundary."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from patchharbor.errors import (
    PatchHarborError,
    unsupported_repository_state_error,
)
from patchharbor.models import RepositoryPath


_WINDOWS_INVALID_PATH_CHARACTERS = frozenset('<>:"\\|?*')
_RESERVED_WINDOWS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$", "clock$"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


def _unsupported_path() -> PatchHarborError:
    return unsupported_repository_state_error(
        "repository contains a non-portable path"
    )


@dataclass(frozen=True, order=True)
class RepositoryRelativePath:
    """One validated path with original bytes and derived portable views."""

    original_bytes: bytes
    decoded: str = field(init=False, compare=False)
    parts: tuple[str, ...] = field(init=False, compare=False)
    collision_key: str = field(init=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.original_bytes, bytes):
            raise TypeError("repository path must be bytes")
        try:
            decoded = self.original_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise _unsupported_path() from exc

        parts = tuple(decoded.split("/"))
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise _unsupported_path()

        for part in parts:
            if any(
                ord(character) <= 0x1F or ord(character) == 0x7F
                for character in part
            ):
                raise _unsupported_path()
            if any(
                character in _WINDOWS_INVALID_PATH_CHARACTERS
                for character in part
            ):
                raise _unsupported_path()
            if part.endswith((".", " ")):
                raise _unsupported_path()

            folded = part.casefold()
            if folded in (".git", ".patchharbor"):
                raise _unsupported_path()
            if folded.split(".", 1)[0] in _RESERVED_WINDOWS_DEVICE_NAMES:
                raise _unsupported_path()

        object.__setattr__(self, "decoded", decoded)
        object.__setattr__(self, "parts", parts)
        object.__setattr__(self, "collision_key", decoded.casefold())

    def resolve_from(self, repository: RepositoryPath) -> Path:
        """Map the validated POSIX path to one repository filesystem path."""
        return repository.value.joinpath(*self.parts)


def validate_repository_paths(
    paths: Iterable[bytes],
) -> tuple[RepositoryRelativePath, ...]:
    """Validate, de-duplicate, collision-check, and byte-sort paths."""
    by_bytes: dict[bytes, RepositoryRelativePath] = {}
    by_collision_key: dict[str, RepositoryRelativePath] = {}

    for raw in paths:
        path = RepositoryRelativePath(raw)
        previous = by_collision_key.setdefault(path.collision_key, path)
        if previous.original_bytes != path.original_bytes:
            raise _unsupported_path()
        by_bytes.setdefault(path.original_bytes, path)

    return tuple(sorted(by_bytes.values()))
