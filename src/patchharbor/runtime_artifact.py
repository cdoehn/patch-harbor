"""Request-owned runtime provider; importing the API never invokes it."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from patchharbor import __version__
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, PathKind, UnsupportedFileTypeError,
    path_kind, read_stable_regular_file_bounded,
)
from patchharbor.runtime_wheel import (
    CHAT_PATH, MAX_RECIPE_BYTES, RECIPE_PATH, RuntimeDataError, RuntimeLimitError,
    RuntimeRecipe, materialize, parse_recipe, sha256,
)


@dataclass(frozen=True, slots=True)
class RuntimeArtifact:
    recipe: RuntimeRecipe
    wheel_bytes: bytes
    wheel_sha256: str
    chat_template: bytes


@dataclass(frozen=True, slots=True)
class RuntimeProvision:
    status: str
    reason: str | None
    artifact: RuntimeArtifact | None


class RuntimeProvider:
    """Pin one verified capture per request, independent of caches/install writes.

    A new request creates a new provider, so a later modified installation is
    rechecked. A pinned response deliberately remains valid after self-update.
    """

    def __init__(self) -> None:
        self._root = Path(__file__).resolve().parent.parent
        self._lock = Lock()
        self._provision: RuntimeProvision | None = None

    def _read(self, name: str, maximum: int) -> bytes:
        path = self._root
        parts = name.split("/")
        for segment in parts[:-1]:
            path = path / segment
            kind = path_kind(path)
            if kind is PathKind.MISSING:
                raise FileNotFoundError(path)
            if kind is not PathKind.DIRECTORY:
                raise RuntimeDataError("linked or special runtime resource")
        path = path / parts[-1]
        if path_kind(path) is PathKind.MISSING:
            raise FileNotFoundError(path)
        return read_stable_regular_file_bounded(path, max_bytes=maximum).content

    def capture(self) -> RuntimeProvision:
        with self._lock:
            if self._provision is None:
                self._provision = self._capture()
            return self._provision

    def _capture(self) -> RuntimeProvision:
        if self._root.name == "src":
            return RuntimeProvision("unavailable", "source_not_prepared", None)
        try:
            recipe = parse_recipe(self._read(RECIPE_PATH, MAX_RECIPE_BYTES))
            if recipe.version != __version__:
                raise RuntimeDataError("producer version and recipe differ")
            # Retain exactly the template bytes read during this same capture.
            template = b""

            def read(name: str, size: int) -> bytes:
                nonlocal template
                raw = self._read(name, size)
                if name == CHAT_PATH:
                    template = raw
                return raw

            wheel = materialize(recipe, read)
            return RuntimeProvision("embedded", None,
                                    RuntimeArtifact(recipe, wheel, sha256(wheel), template))
        except FileNotFoundError:
            return RuntimeProvision("unavailable", "resources_missing", None)
        except RuntimeLimitError:
            return RuntimeProvision("unavailable", "resource_limit", None)
        except (OSError, RuntimeDataError, FileReadLimitExceeded,
                FileChangedDuringRead, UnsupportedFileTypeError):
            return RuntimeProvision("unavailable", "resources_invalid", None)
