"""Static package facts. No registration, execution or publication lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import os
from pathlib import Path

from patchharbor.bundle_handoff import TASK_HANDOFF_DIRECTORY
from patchharbor.interpreters import select_interpreter
from patchharbor.models import RepositoryContext
from patchharbor.errors import state_mismatch_error
from patchharbor.exchange_state import ExchangeTaskSelection
from patchharbor.result_reader import (
    CapturedResultReference, ReferenceContext, capture_result_reference,
)
from patchharbor.repository_state import capture_repository_context
from patchharbor.parser import Message as TaskMessage
from patchharbor.task_manifest import TASK_MANIFEST_NAME, TaskManifest
from patchharbor.task_package import ValidatedTaskBundle, parse_task_entrypoint, resolve_task_bundle
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


class TaskEntryRole(str, Enum):
    MANIFEST = "manifest"
    ENTRYPOINT = "entrypoint"
    PAYLOAD = "payload"
    HANDOFF = "handoff"


class TaskValidationScope(str, Enum):
    PACKAGE = "package"
    REFERENCE = "reference"
    REPOSITORY = "repository"


@dataclass(frozen=True, slots=True)
class TaskEntry:
    """Observed bytes; the digest is not a declared manifest checksum."""

    path: str
    role: TaskEntryRole
    size: int
    sha256: str
    unix_mode: int | None


@dataclass(frozen=True, slots=True)
class TaskInspection:
    """Immutable facts derived from one stable archive read, without payload bytes."""

    package_sha256: str
    package_size: int
    manifest: TaskManifest
    entrypoint: str
    entries: tuple[TaskEntry, ...]
    messages: tuple[TaskMessage, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TaskValidationResult:
    """Static validity, explicitly separate from binding and authenticity."""

    inspection: TaskInspection
    scope: TaskValidationScope
    binding_matches: bool | None
    context: RepositoryContext | ReferenceContext | None
    reference_sha256: str | None
    checked_at: datetime
    not_checked: tuple[str, ...]


def inspect_task(
    path: Path, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
    expected_identity: os.stat_result | None = None,
) -> TaskInspection:
    owned = {} if expected_identity is None else {'expected_identity': expected_identity}
    package = resolve_task_bundle(path, resource_policy=resource_policy, **owned)
    return inspect_captured_task(package)


def inspect_captured_task(package: ValidatedTaskBundle) -> TaskInspection:
    """Project static facts from owned bytes, including locked admission callers."""
    script = parse_task_entrypoint(package.entrypoint)
    # Whitelist the syntax, but do not look for an installed shell.
    select_interpreter(script.text)
    if package.package_sha256 is None or package.package_size is None:
        raise RuntimeError("static inspection requires a captured package")
    entries = []
    for payload in package.entries:
        name = payload.relative_path
        if name == TASK_MANIFEST_NAME:
            role = TaskEntryRole.MANIFEST
        elif name == package.entrypoint.relative_path:
            role = TaskEntryRole.ENTRYPOINT
        elif name.startswith(TASK_HANDOFF_DIRECTORY + "/"):
            role = TaskEntryRole.HANDOFF
        else:
            role = TaskEntryRole.PAYLOAD
        entries.append(TaskEntry(name, role, len(payload.content),
                                  sha256(payload.content).hexdigest(), payload.unix_mode))
    return TaskInspection(
        package.package_sha256, package.package_size, package.manifest,
        package.entrypoint.relative_path, tuple(sorted(entries, key=lambda entry: entry.path)),
        script.messages, package.warnings + script.warnings,
    )


def validate_task(
    path: Path, *, repository: Path | None = None, reference_bundle: Path | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> TaskValidationResult:
    if repository is not None and reference_bundle is not None:
        raise ValueError("repository and reference_bundle are mutually exclusive")
    inspection = inspect_task(path, resource_policy=resource_policy)
    if reference_bundle is not None:
        reference = capture_result_reference(reference_bundle, resource_policy=resource_policy)
        return _validation_result(inspection, scope=TaskValidationScope.REFERENCE,
                                  context=reference.facts.context, reference_sha256=reference.sha256)
    if repository is not None:
        context = capture_repository_context(repository, read_only=True)
        return _validation_result(inspection, scope=TaskValidationScope.REPOSITORY, context=context)
    return _validation_result(inspection, scope=TaskValidationScope.PACKAGE)


def validate_task_against_reference(
    path: Path, reference: CapturedResultReference, *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
    expected_identity: os.stat_result | None = None,
) -> TaskValidationResult:
    """Internal pack seam: inspect actual package bytes against one captured Result.

    Callers must obtain the reference from capture_result_reference in the same
    request. This avoids another reference-path read, not the package inspection
    or the common binding check. Public APIs continue to accept explicit paths.
    """
    owned = {} if expected_identity is None else {'expected_identity': expected_identity}
    inspection = inspect_task(path, resource_policy=resource_policy, **owned)
    return _validation_result(inspection, scope=TaskValidationScope.REFERENCE,
                              context=reference.facts.context, reference_sha256=reference.sha256)


def _validation_result(
    inspection: TaskInspection, *, scope: TaskValidationScope,
    context: RepositoryContext | ReferenceContext | None = None,
    reference_sha256: str | None = None,
) -> TaskValidationResult:
    """One binding check and one set of scope/not-checked facts for both paths."""
    not_checked = ("authenticity", "execution", "interpreter_availability", "tests", "ci", "replay")
    if scope is TaskValidationScope.REFERENCE:
        not_checked += ("live_repository_state", "local_registration", "reconstructed_state_fingerprint",
                        "legacy_delta_log_hashes")
    elif scope is TaskValidationScope.REPOSITORY:
        not_checked += ("future_repository_state",)
    else:
        not_checked += ("repository_binding", "repository_state")
    if context is not None:
        if not ExchangeTaskSelection.from_manifest(inspection.manifest).matches_context(context):
            raise state_mismatch_error("patch binding does not match the explicitly selected context")
    return TaskValidationResult(
        inspection, scope, None if context is None else True, context, reference_sha256,
        datetime.now(timezone.utc), not_checked,
    )
