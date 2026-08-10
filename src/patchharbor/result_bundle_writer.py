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


def write_result_bundle(
    path: Path,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_document: dict[str, object],
    base_entries: tuple[BaseBundleEntry, ...],
) -> None:
    """Write one fully captured base-only Result Bundle."""
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            archive.writestr(_zip_info("manifest.json"), _json_bytes(manifest))
            archive.writestr(
                _zip_info("context.json"),
                _json_bytes(context_document),
            )
            archive.writestr(
                _zip_info("logs/run.json"),
                _json_bytes(run_document),
            )
            for entry in base_entries:
                archive.writestr(
                    _zip_info(
                        f"base/{entry.path.decoded}",
                        executable=entry.executable,
                    ),
                    entry.content,
                )
    except (OSError, RuntimeError, ValueError, zipfile.LargeZipFile) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise result_bundle_error("cannot create the Result Bundle") from exc
