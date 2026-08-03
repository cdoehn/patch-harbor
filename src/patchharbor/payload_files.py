"""Validation and atomic writing of PatchHarbor payload files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from patchharbor.bundle_paths import (
    BundlePathError,
    is_safe_path_segment,
    validate_bundle_member_paths,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    create_directory,
    path_kind,
)


def _write_error(label: str, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot write {label}: {detail}",
        ExitCode.PAYLOAD_PREPARATION_ERROR,
    )


def _file_error(name: str, detail: object) -> PatchHarborError:
    return _write_error(f"FILE {name!r}", detail)


def _bundle_file_error(relative_path: str, detail: object) -> PatchHarborError:
    return _write_error(f"bundle file {relative_path!r}", detail)


def is_safe_payload_name(name: str) -> bool:
    """Return whether a FILE name is a portable, path-free file name."""
    return is_safe_path_segment(name)


def payload_size_warning(
    name: str,
    text: str,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> str | None:
    """Enforce the shared hard budget and return an optional soft warning."""
    size_bytes = len(text.encode("utf-8"))
    if size_bytes > policy.max_content_bytes:
        raise PatchHarborError(
            f"FILE {name!r} exceeds the "
            f"{policy.max_content_bytes} byte limit",
            ExitCode.SOURCE_ERROR,
        )
    return policy.large_content_warning(f"FILE {name!r}", size_bytes)


def prepare_payload_files(
    payloads: Iterable[tuple[str, str]],
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Filter optional FILE descriptions without touching the filesystem."""
    prepared: list[tuple[str, str]] = []
    warnings: list[str] = []

    for name, text in payloads:
        if not is_safe_payload_name(name):
            warnings.append(f"discarded FILE {name!r}: invalid file name")
            continue
        if warning := payload_size_warning(name, text, policy=policy):
            warnings.append(warning)
        prepared.append((name, text))

    return tuple(prepared), tuple(warnings)


def _kind_or_error(target: Path, *, label: str) -> PathKind:
    try:
        return path_kind(target)
    except FileSystemOperationError as exc:
        raise _write_error(label, exc.operation) from exc


def _validate_regular_target(target: Path, *, label: str) -> None:
    kind = _kind_or_error(target, label=label)
    if kind in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        return
    raise _write_error(label, "target is not a regular file")


def _replace_bytes(target: Path, content: bytes, *, label: str) -> None:
    try:
        atomic_replace_bytes(target, content)
    except FileSystemOperationError as exc:
        raise _write_error(label, exc.operation) from exc


def _bundle_target(
    cwd: Path,
    relative_path: str,
    *,
    create_parents: bool,
) -> Path:
    target = cwd
    segments = relative_path.split("/")
    label = f"bundle file {relative_path!r}"

    for segment in segments[:-1]:
        target /= segment
        kind = _kind_or_error(target, label=label)
        if kind is PathKind.MISSING:
            if not create_parents:
                return cwd.joinpath(*segments)
            try:
                create_directory(target)
            except FileSystemOperationError as exc:
                raise _write_error(label, exc.operation) from exc
            continue
        if kind is PathKind.DIRECTORY:
            continue
        raise _write_error(label, "parent is not a directory")

    final_target = target / segments[-1]
    _validate_regular_target(final_target, label=label)
    return final_target


def write_bundle_payloads(
    payloads: Iterable[BundlePayload],
    *,
    cwd: Path,
) -> None:
    """Validate all ZIP payloads, then atomically write their byte content."""
    payload_items = tuple(payloads)
    if not payload_items:
        return

    try:
        validate_bundle_member_paths(
            (payload.relative_path, False) for payload in payload_items
        )
    except BundlePathError as exc:
        raise _bundle_file_error("<bundle>", exc) from exc

    for payload in payload_items:
        _bundle_target(
            cwd,
            payload.relative_path,
            create_parents=False,
        )

    for payload in payload_items:
        target = _bundle_target(
            cwd,
            payload.relative_path,
            create_parents=True,
        )
        _replace_bytes(
            target,
            payload.content,
            label=f"bundle file {payload.relative_path!r}",
        )


def write_payload_files(
    payloads: Iterable[tuple[str, str]],
    *,
    cwd: Path,
) -> None:
    """Atomically write validated FILE payloads into the working directory."""
    for name, text in payloads:
        if not is_safe_payload_name(name):
            raise _file_error(name, "unsafe file name")
        target = cwd / name
        label = f"FILE {name!r}"
        _validate_regular_target(target, label=label)
        _replace_bytes(
            target,
            text.encode("utf-8"),
            label=label,
        )
