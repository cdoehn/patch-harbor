"""Validation and atomic writing of ZIP bundle payload files."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from patchharbor.progress import activity

from patchharbor.bundle_paths import (
    BundlePathError,
    validate_bundle_member_paths,
)
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.models import BundlePayload
from patchharbor.payload_modes import select_payload_mode
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    create_directory,
    path_kind,
    RegularFileState,
    regular_file_state,
)


class PayloadTargetError(PatchHarborError):
    """A bundle target is unsafe before its replacement is staged."""


class PayloadWriteError(PatchHarborError):
    """A checked bundle target could not be created or replaced."""


def _target_error(label: str, detail: object) -> PayloadTargetError:
    return PayloadTargetError(
        f"cannot write {label}: {detail}",
        FailureReason.PAYLOAD_PREPARATION_ERROR,
    )


def _write_error(label: str, detail: object) -> PayloadWriteError:
    return PayloadWriteError(
        f"cannot write {label}: {detail}",
        FailureReason.PAYLOAD_PREPARATION_ERROR,
    )


def _bundle_file_error(relative_path: str, detail: object) -> PayloadTargetError:
    return _target_error(f"bundle file {relative_path!r}", detail)


def _kind_or_error(target: Path, *, label: str) -> PathKind:
    try:
        return path_kind(target)
    except FileSystemOperationError as exc:
        raise _target_error(label, exc.operation) from exc


def _replace_bytes(
    target: Path, content: bytes, *, label: str, mode: int,
    before_replace: Callable[[], None],
) -> None:
    try:
        activity("WRITE", f"Atomically write: {target} ({len(content)} bytes)")
        atomic_replace_bytes(target, content, mode=mode, before_replace=before_replace)
        activity("WRITE", f"Written: {target}", "success")
    except FileSystemOperationError as exc:
        raise _write_error(label, exc.operation) from exc


def _resolve_payload_target(
    cwd: Path,
    relative_path: str,
    *,
    create_parents: bool,
) -> Path:
    activity("TARGET", f"Validate repository target: {relative_path}")
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
                activity("MKDIR", f"Create payload parent directory: {target}")
                create_directory(target)
            except FileSystemOperationError as exc:
                raise _write_error(label, exc.operation) from exc
            continue
        if kind is PathKind.DIRECTORY:
            continue
        raise _target_error(label, "parent is not a directory")

    final_target = target / segments[-1]
    final_kind = _kind_or_error(final_target, label=label)
    if final_kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _target_error(label, "target is not a regular file")
    return final_target


@dataclass(frozen=True, slots=True)
class _PayloadTarget:
    path: Path
    state: RegularFileState | None
    mode: int


def _inspect_payload_target(
    cwd: Path, payload: BundlePayload, *, create_parents: bool,
) -> _PayloadTarget:
    path = _resolve_payload_target(cwd, payload.relative_path, create_parents=create_parents)
    try:
        select_payload_mode(payload.unix_mode, None)
        state = regular_file_state(path)
        mode = select_payload_mode(payload.unix_mode, None if state is None else state.mode)
        return _PayloadTarget(path, state, mode)
    except (ValueError, FileSystemOperationError) as exc:
        raise _bundle_file_error(payload.relative_path, str(exc)) from exc


def _require_unchanged_target(
    cwd: Path, payload: BundlePayload, expected: RegularFileState | None,
) -> None:
    # Re-resolve parents as well; a symlink/junction introduced during staging
    # must not redirect publication. This is a final observation, not an OS
    # compare-and-swap guarantee against hostile concurrent filesystem access.
    target = _inspect_payload_target(cwd, payload, create_parents=False)
    if target.state != expected:
        raise _bundle_file_error(payload.relative_path, "target changed during staging")


def validate_bundle_payload_targets(
    payloads: Iterable[BundlePayload],
    *,
    cwd: Path,
) -> tuple[BundlePayload, ...]:
    """Validate current parents and targets without creating repository files."""
    payload_items = tuple(payloads)
    if not payload_items:
        return payload_items

    try:
        validate_bundle_member_paths(
            (payload.relative_path, False) for payload in payload_items
        )
    except BundlePathError as exc:
        raise _bundle_file_error("<bundle>", exc) from exc

    for payload in payload_items:
        _inspect_payload_target(cwd, payload, create_parents=False)
    return payload_items


def write_bundle_payloads(
    payloads: Iterable[BundlePayload],
    *,
    cwd: Path,
) -> None:
    """Validate every target, then atomically replace each file in order.

    Successful earlier replacements remain when a later payload fails.
    """
    payload_items = validate_bundle_payload_targets(payloads, cwd=cwd)
    if not payload_items:
        return

    activity("PAYLOAD", f"Write {len(payload_items)} payload file(s)", "heading")
    for payload in payload_items:
        target = _inspect_payload_target(cwd, payload, create_parents=True)
        _replace_bytes(
            target.path,
            payload.content,
            label=f"bundle file {payload.relative_path!r}",
            mode=target.mode,
            before_replace=partial(_require_unchanged_target, cwd, payload, target.state),
        )
    activity("PAYLOAD", f"Wrote {len(payload_items)} payload file(s)", "success")
