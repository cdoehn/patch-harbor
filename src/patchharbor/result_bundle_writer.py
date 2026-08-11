"""Write already captured PatchHarbor Result Bundle data to one ZIP."""

from __future__ import annotations

import json
from pathlib import Path
import stat
import zipfile

from patchharbor.errors import result_bundle_error
from patchharbor.git_objects import BaseBundleEntry


def _json_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _zip_info(name: str, *, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    permissions = 0o755 if executable else 0o644
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | permissions) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _write_entry(
    archive: zipfile.ZipFile,
    name: str,
    content: bytes | memoryview,
    *,
    executable: bool = False,
) -> None:
    archive.writestr(
        _zip_info(name, executable=executable),
        content,
    )


def write_result_bundle(
    path: Path,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_document: dict[str, object],
    base_entries: tuple[BaseBundleEntry, ...],
    staged_patch: bytes,
    unstaged_patch: bytes,
) -> None:
    """Write one fully captured Result Bundle."""
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for name, document in (
                ("manifest.json", manifest),
                ("context.json", context_document),
                ("logs/run.json", run_document),
            ):
                _write_entry(archive, name, _json_bytes(document))
            for entry in base_entries:
                _write_entry(
                    archive,
                    f"base/{entry.path.decoded}",
                    entry.content,
                    executable=entry.executable,
                )
            _write_entry(archive, "changes/staged.patch", staged_patch)
            _write_entry(archive, "changes/unstaged.patch", unstaged_patch)
    except (OSError, RuntimeError, ValueError, zipfile.LargeZipFile) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise result_bundle_error("cannot create the Result Bundle") from exc
