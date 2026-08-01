"""Validation and atomic writing of inline PatchHarbor FILE payloads."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import re
import stat
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload


PAYLOAD_WARNING_BYTES = 10 * 1024 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024 * 1024
_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _file_error(name: str, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot write FILE {name!r}: {detail}",
        ExitCode.FILE_PREPARATION_ERROR,
    )


def is_safe_payload_name(name: str) -> bool:
    """Return whether a FILE name is a portable, path-free file name."""
    if _FILENAME_PATTERN.fullmatch(name) is None:
        return False
    if name in {".", ".."} or name.endswith((".", " ")):
        return False
    return name.split(".", 1)[0].upper() not in _WINDOWS_RESERVED_NAMES


def is_safe_bundle_path(relative_path: str) -> bool:
    """Return whether a ZIP payload path stays below the working directory."""
    if (
        not relative_path
        or len(relative_path) > 512
        or relative_path.startswith("/")
        or "\\" in relative_path
    ):
        return False

    return all(
        is_safe_payload_name(segment)
        for segment in relative_path.split("/")
    )


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


def _replace_bytes(
    target: Path,
    content: bytes,
    *,
    relative_path: str,
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
        raise _bundle_file_error(relative_path, exc) from exc
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


def write_bundle_payloads(
    payloads: Iterable[BundlePayload],
    *,
    cwd: Path,
) -> None:
    """Write ZIP payload bytes before the first bundle script executes."""
    for payload in payloads:
        if not is_safe_bundle_path(payload.relative_path):
            raise _bundle_file_error(
                payload.relative_path,
                "unsafe relative path",
            )
        target = _ensure_bundle_parent(cwd, payload.relative_path)
        _validate_target(target, name=payload.relative_path)
        _replace_bytes(
            target,
            payload.content,
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
