"""Validation and atomic writing of PatchHarbor payload files."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import stat
import tempfile

from patchharbor.bundle_paths import (
    BundlePathError,
    is_safe_path_segment,
    validate_bundle_member_paths,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload


PAYLOAD_WARNING_BYTES = 10 * 1024 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024 * 1024


def _write_error(label: str, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot write {label}: {detail}",
        ExitCode.FILE_PREPARATION_ERROR,
    )


def _file_error(name: str, detail: object) -> PatchHarborError:
    return _write_error(f"FILE {name!r}", detail)


def _bundle_file_error(relative_path: str, detail: object) -> PatchHarborError:
    return _write_error(f"bundle file {relative_path!r}", detail)


def is_safe_payload_name(name: str) -> bool:
    """Return whether a FILE name is a portable, path-free file name."""
    return is_safe_path_segment(name)


def payload_size_warning(name: str, text: str) -> str | None:
    """Enforce the hard FILE budget and return an optional soft warning."""
    size_bytes = len(text.encode("utf-8"))
    if size_bytes > MAX_PAYLOAD_BYTES:
        raise PatchHarborError(
            f"FILE {name!r} exceeds the {MAX_PAYLOAD_BYTES} byte limit",
            ExitCode.SOURCE_ERROR,
        )
    if size_bytes > PAYLOAD_WARNING_BYTES:
        return f"FILE {name!r} is large ({size_bytes} bytes)"
    return None


def prepare_payload_files(
    payloads: Iterable[tuple[str, str]],
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Filter optional FILE descriptions without touching the filesystem."""
    prepared: list[tuple[str, str]] = []
    warnings: list[str] = []

    for name, text in payloads:
        if not is_safe_payload_name(name):
            warnings.append(f"discarded FILE {name!r}: invalid file name")
            continue
        if warning := payload_size_warning(name, text):
            warnings.append(warning)
        prepared.append((name, text))

    return tuple(prepared), tuple(warnings)


def _validate_regular_target(target: Path, *, label: str) -> None:
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _write_error(label, exc) from exc

    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _write_error(label, "target is not a regular file")


def _atomic_replace_bytes(
    target: Path,
    content: bytes,
    *,
    label: str,
) -> None:
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".patchharbor-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            staged_path = Path(handle.name)
            handle.write(content)
        os.replace(staged_path, target)
        staged_path = None
    except OSError as exc:
        raise _write_error(label, exc) from exc
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


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
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            if not create_parents:
                return cwd.joinpath(*segments)
            try:
                target.mkdir()
            except OSError as exc:
                raise _write_error(label, exc) from exc
            continue
        except OSError as exc:
            raise _write_error(label, exc) from exc

        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
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
        _atomic_replace_bytes(
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
        _atomic_replace_bytes(
            target,
            text.encode("utf-8"),
            label=label,
        )
