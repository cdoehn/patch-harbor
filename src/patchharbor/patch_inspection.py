"""Static package facts. No registration, execution or publication lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path

from patchharbor.bundle_handoff import PATCH_HANDOFF_DIRECTORY
from patchharbor.interpreters import select_interpreter
from patchharbor.models import RepositoryContext
from patchharbor.parser import Message as PatchMessage
from patchharbor.patch_manifest import PATCH_MANIFEST_NAME, PatchManifest
from patchharbor.patch_package import parse_package_entrypoint, resolve_patch_package
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


class PatchEntryRole(str, Enum):
    MANIFEST = "manifest"
    ENTRYPOINT = "entrypoint"
    PAYLOAD = "payload"
    HANDOFF = "handoff"


class PatchValidationScope(str, Enum):
    PACKAGE = "package"


@dataclass(frozen=True, slots=True)
class PatchEntry:
    """Observed bytes; the digest is not a declared manifest checksum."""

    path: str
    role: PatchEntryRole
    size: int
    sha256: str
    unix_mode: int | None


@dataclass(frozen=True, slots=True)
class PatchInspection:
    """Immutable facts derived from one stable archive read, without payload bytes."""

    package_sha256: str
    package_size: int
    manifest: PatchManifest
    entrypoint: str
    entries: tuple[PatchEntry, ...]
    messages: tuple[PatchMessage, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatchValidationResult:
    """Static validity, explicitly separate from binding and authenticity."""

    inspection: PatchInspection
    scope: PatchValidationScope
    binding_matches: bool | None
    context: RepositoryContext | None
    reference_sha256: str | None
    checked_at: datetime
    not_checked: tuple[str, ...]


def inspect_patch(
    path: Path, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchInspection:
    package = resolve_patch_package(path, resource_policy=resource_policy)
    script = parse_package_entrypoint(package.entrypoint)
    # Whitelist the syntax, but do not look for an installed shell.
    select_interpreter(script.text)
    if package.package_sha256 is None or package.package_size is None:
        raise RuntimeError("static inspection requires a captured package")
    entries = []
    for payload in package.entries:
        name = payload.relative_path
        if name == PATCH_MANIFEST_NAME:
            role = PatchEntryRole.MANIFEST
        elif name == package.entrypoint.relative_path:
            role = PatchEntryRole.ENTRYPOINT
        elif name.startswith(PATCH_HANDOFF_DIRECTORY + "/"):
            role = PatchEntryRole.HANDOFF
        else:
            role = PatchEntryRole.PAYLOAD
        entries.append(PatchEntry(name, role, len(payload.content),
                                  sha256(payload.content).hexdigest(), payload.unix_mode))
    return PatchInspection(
        package.package_sha256, package.package_size, package.manifest,
        package.entrypoint.relative_path, tuple(sorted(entries, key=lambda entry: entry.path)),
        script.messages, package.warnings + script.warnings,
    )


def validate_patch(
    path: Path, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchValidationResult:
    inspection = inspect_patch(path, resource_policy=resource_policy)
    return PatchValidationResult(
        inspection, PatchValidationScope.PACKAGE, None, None, None,
        datetime.now(timezone.utc),
        ("repository_binding", "repository_state", "authenticity", "execution",
         "interpreter_availability", "tests", "ci", "replay"),
    )
