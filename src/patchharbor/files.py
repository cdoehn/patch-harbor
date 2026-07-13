"""Temporary file preparation for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError


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


def write_payload_files(
    payloads: Iterable[tuple[str, str]],
    *,
    cwd: Path,
) -> None:
    """Write valid FILE payloads into the script working directory."""
    for name, text in payloads:
        target = cwd / name
        try:
            target.write_text(text, encoding="utf-8", newline="")
        except OSError as exc:
            raise PatchHarborError(
                f"cannot write FILE {name!r}: {exc}",
                ExitCode.FILE_PREPARATION_ERROR,
            ) from exc
