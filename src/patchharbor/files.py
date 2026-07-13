"""Temporary and transferred file preparation for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError


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


@contextmanager
def temporary_script_file(script_text: str, *, suffix: str) -> Iterator[Path]:
    """Write script text to a secure system-temp file and remove it afterwards."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=suffix,
        text=True,
    )
    script_path = Path(raw_path)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(script_text)
        yield script_path
    finally:
        script_path.unlink(missing_ok=True)


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


def payload_size_warning(name: str, lines: Iterable[str]) -> str | None:
    """Enforce the hard FILE budget without encoding the full payload twice."""
    size_bytes = 0
    for index, line in enumerate(lines):
        if index:
            size_bytes += 1
        size_bytes += len(line.encode("utf-8"))
        if size_bytes > MAX_PAYLOAD_BYTES:
            raise PatchHarborError(
                f"FILE {name!r} exceeds the {MAX_PAYLOAD_BYTES} byte limit",
                ExitCode.SOURCE_ERROR,
            )
    if size_bytes > PAYLOAD_WARNING_BYTES:
        return f"FILE {name!r} is large ({size_bytes} bytes)"
    return None


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
