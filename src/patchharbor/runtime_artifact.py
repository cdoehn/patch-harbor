"""Request-owned runtime provider; importing the API never invokes it."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from patchharbor import __version__, _runtime_resource_id
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError,
    read_stable_regular_file_bounded,
)
from patchharbor.runtime_sources import read_directory_resource
from patchharbor.runtime_wheel import (
    CHAT_PATH, IDENTITY_PATH, MAX_RECIPE_BYTES, RECIPE_PATH, RuntimeDataError, RuntimeLimitError,
    RuntimeRecipe, materialize, parse_recipe, producer_id, sha256,
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
        self._producer_id = _runtime_resource_id
        self._lock = Lock()
        self._provision: RuntimeProvision | None = None

    def _read(self, name: str, maximum: int) -> bytes:
        return read_directory_resource(self._root, name, maximum,
                                       read_file=read_stable_regular_file_bounded)

    def capture(self) -> RuntimeProvision:
        with self._lock:
            if self._provision is None:
                self._provision = self._capture()
            return self._provision

    def _capture(self) -> RuntimeProvision:
        if self._producer_id is None:
            return RuntimeProvision("unavailable", "source_not_prepared", None)
        try:
            try:
                recipe_data = self._read(RECIPE_PATH, MAX_RECIPE_BYTES)
            except FileReadLimitExceeded as exc:
                raise RuntimeLimitError("runtime recipe too large") from exc
            recipe = parse_recipe(recipe_data)
            if recipe.version != __version__:
                raise RuntimeDataError("producer version and recipe differ")
            if (producer_id(recipe) != self._producer_id
                    or IDENTITY_PATH not in {entry.path for entry in recipe.entries}):
                return RuntimeProvision("unavailable", "source_changed", None)
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
