"""Validation and atomic writing of ZIP bundle payload files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from patchharbor.bundle_paths import (
    BundlePathError,
    validate_bundle_member_paths,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload
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


def _bundle_file_error(relative_path: str, detail: object) -> PatchHarborError:
    return _write_error(f"bundle file {relative_path!r}", detail)


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
