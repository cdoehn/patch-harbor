"""Validation, staging, and atomic writing of PatchHarbor payload files."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import shutil
import stat
import tempfile

from patchharbor.bundle_paths import (
    BundlePathError,
    is_safe_bundle_path,
    is_safe_path_segment,
    validate_bundle_member_paths,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload


PAYLOAD_WARNING_BYTES = 10 * 1024 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024 * 1024
_COPY_CHUNK_BYTES = 64 * 1024


def _file_error(name: str, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot write FILE {name!r}: {detail}",
        ExitCode.FILE_PREPARATION_ERROR,
    )


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


def _validate_target(target: Path, *, name: str) -> None:
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _file_error(name, exc) from exc

    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _file_error(name, "target is not a regular file")


def _replace_text(target: Path, text: str, *, name: str) -> None:
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            prefix=".patchharbor-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            staged_path = Path(handle.name)
            handle.write(text)
        os.replace(staged_path, target)
        staged_path = None
    except OSError as exc:
        raise _file_error(name, exc) from exc
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


def _bundle_file_error(relative_path: str, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot write bundle file {relative_path!r}: {detail}",
        ExitCode.FILE_PREPARATION_ERROR,
    )


def _validate_bundle_target(cwd: Path, relative_path: str) -> Path:
    target = cwd
    segments = relative_path.split("/")

    for segment in segments[:-1]:
        target /= segment
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            return cwd.joinpath(*segments)
        except OSError as exc:
            raise _bundle_file_error(relative_path, exc) from exc

        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise _bundle_file_error(
                relative_path,
                "parent is not a directory",
            )

    final_target = target / segments[-1]
    _validate_bundle_file_target(final_target, relative_path=relative_path)
    return final_target


def _validate_bundle_file_target(
    target: Path,
    *,
    relative_path: str,
) -> None:
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _bundle_file_error(relative_path, exc) from exc

    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise _bundle_file_error(
            relative_path,
            "target is not a regular file",
        )


def _ensure_bundle_parent(cwd: Path, relative_path: str) -> Path:
    target = cwd
    segments = relative_path.split("/")

    for segment in segments[:-1]:
        target /= segment
        try:
            mode = target.lstat().st_mode
        except FileNotFoundError:
            try:
                target.mkdir()
            except OSError as exc:
                raise _bundle_file_error(relative_path, exc) from exc
            continue
        except OSError as exc:
            raise _bundle_file_error(relative_path, exc) from exc

        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise _bundle_file_error(
                relative_path,
                "parent is not a directory",
            )

    return target / segments[-1]


def _stage_bundle_payload(
    stage_root: Path,
    payload: BundlePayload,
) -> Path:
    target = stage_root.joinpath(*payload.relative_path.split("/"))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(payload.content)
    except OSError as exc:
        raise _bundle_file_error(payload.relative_path, exc) from exc
    return target


def _replace_staged_bytes(
    target: Path,
    staged_source: Path,
    *,
    relative_path: str,
) -> None:
    local_stage: Path | None = None
    try:
        with staged_source.open("rb") as source, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".patchharbor-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            local_stage = Path(handle.name)
            shutil.copyfileobj(source, handle, length=_COPY_CHUNK_BYTES)
        os.replace(local_stage, target)
        local_stage = None
    except OSError as exc:
        raise _bundle_file_error(relative_path, exc) from exc
    finally:
        if local_stage is not None:
            local_stage.unlink(missing_ok=True)


def write_bundle_payloads(
    payloads: Iterable[BundlePayload],
    *,
    cwd: Path,
) -> None:
    """Stage every ZIP payload before writing any target or running a script."""
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
        _validate_bundle_target(cwd, payload.relative_path)

    try:
        staging_directory = tempfile.TemporaryDirectory(
            prefix="patchharbor-bundle-stage-"
        )
    except OSError as exc:
        raise _bundle_file_error("<bundle>", exc) from exc

    with staging_directory as raw_stage_root:
        stage_root = Path(raw_stage_root)
        staged_payloads = tuple(
            (
                payload,
                _stage_bundle_payload(stage_root, payload),
            )
            for payload in payload_items
        )

        for payload, staged_source in staged_payloads:
            target = _ensure_bundle_parent(cwd, payload.relative_path)
            _validate_bundle_file_target(
                target,
                relative_path=payload.relative_path,
            )
            _replace_staged_bytes(
                target,
                staged_source,
                relative_path=payload.relative_path,
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
        _validate_target(target, name=name)
        _replace_text(target, text, name=name)
