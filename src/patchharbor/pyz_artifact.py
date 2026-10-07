"""Request-owned, installation-free capture of the loaded PYZ producer profile."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from threading import Lock
from zipfile import ZipFile

from patchharbor import __version__, _pyz_resource_id
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError,
    PathKind, path_kind,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.runtime_pyz import (
    CHAT_PATH, DOC_PATH, LICENSE_PATH, RECIPE_PATH, MAX_RECIPE_BYTES,
    MAX_PYZ_BYTES, MAX_CONTENT_BYTES, PyzRecipe, RuntimeDataError, RuntimeLimitError,
    materialize, parse_recipe, producer_id, read_pyz, sha256,
)
from patchharbor.runtime_sources import ZipResources, own_resources


def own_pyz_profile_present() -> bool:
    """A missing loaded identity cannot silently select a legacy fallback.

    Clean source trees and canonical legacy installations have no PYZ recipe.
    ZIP execution is always explicit and must satisfy its selected profile.
    """
    if _pyz_resource_id is not None:
        return True
    source = own_resources()
    return (isinstance(source, ZipResources)
            or path_kind(source.root / RECIPE_PATH) is not PathKind.MISSING)


@dataclass(frozen=True, slots=True)
class PyzArtifact:
    recipe: PyzRecipe
    pyz_bytes: bytes
    pyz_sha256: str
    chat_template: bytes
    api_documentation: bytes
    license: bytes


@dataclass(frozen=True, slots=True)
class PyzProvision:
    status: str
    reason: str | None
    artifact: PyzArtifact | None


class PyzProvider:
    """Capture once; neither build nor cache nor extract while handling a request."""

    def __init__(self) -> None:
        self._producer_id = _pyz_resource_id
        self._lock = Lock()
        self._provision: PyzProvision | None = None

    def capture(self) -> PyzProvision:
        with self._lock:
            if self._provision is None:
                self._provision = self._capture()
            return self._provision

    def _capture(self) -> PyzProvision:
        if self._producer_id is None:
            return PyzProvision('unavailable', 'source_not_prepared', None)
        try:
            source = own_resources()
            if isinstance(source, ZipResources):
                raw = source.capture(MAX_PYZ_BYTES)
                recipe = read_pyz(raw, policy=DEFAULT_RESOURCE_POLICY,
                                  remaining_bytes=MAX_CONTENT_BYTES)
            else:
                recipe = parse_recipe(source.read(RECIPE_PATH, MAX_RECIPE_BYTES))
                raw = None
            if recipe.version != __version__:
                raise RuntimeDataError('producer version and PYZ recipe differ')
            if producer_id(recipe) != self._producer_id:
                return PyzProvision('unavailable', 'source_changed', None)
            if raw is None:
                raw = materialize(recipe, source.read)
            # At this point both input forms have passed the complete same data
            # profile. Read the exact documents from these pinned canonical bytes.
            with ZipFile(BytesIO(raw)) as archive:
                documents = tuple(archive.read(name) for name in (CHAT_PATH, DOC_PATH, LICENSE_PATH))
            return PyzProvision('embedded', None,
                                PyzArtifact(recipe, raw, sha256(raw), *documents))
        except FileNotFoundError:
            return PyzProvision('unavailable', 'resources_missing', None)
        except (RuntimeLimitError, FileReadLimitExceeded):
            return PyzProvision('unavailable', 'resource_limit', None)
        except (OSError, RuntimeDataError, FileChangedDuringRead, UnsupportedFileTypeError):
            return PyzProvision('unavailable', 'resources_invalid', None)
