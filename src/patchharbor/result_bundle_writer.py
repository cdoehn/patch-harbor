"""Write one already captured PatchHarbor Result Bundle to a ZIP."""

from __future__ import annotations

import stat
import zipfile
from typing import BinaryIO

from patchharbor.errors import result_bundle_error
from patchharbor.json_document import serialize_json_document
from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
from patchharbor.run_report import RunReport


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
    destination: BinaryIO,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_report: RunReport,
    snapshot: ResultBundleSnapshot,
) -> None:
    """Write one captured Result Bundle to a caller-owned binary stream."""
    try:
        with zipfile.ZipFile(
            destination,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for name, document in (
                ("manifest.json", manifest),
                ("context.json", context_document),
                ("logs/run.json", run_report.as_run_document()),
            ):
                _write_entry(
                    archive,
                    name,
                    serialize_json_document(document).encode("utf-8"),
                )
            for entry in snapshot.base_entries:
                _write_entry(
                    archive,
                    f"base/{entry.path.decoded}",
                    entry.content,
                    executable=entry.executable,
                )
            _write_entry(
                archive,
                "changes/staged.patch",
                snapshot.staged_patch,
            )
            _write_entry(
                archive,
                "changes/unstaged.patch",
                snapshot.unstaged_patch,
            )
            for entry in snapshot.untracked_entries:
                _write_entry(
                    archive,
                    f"untracked/{entry.path.decoded}",
                    entry.content,
                    executable=entry.executable,
                )
    except (OSError, RuntimeError, ValueError, zipfile.LargeZipFile) as exc:
        raise result_bundle_error("cannot create the Result Bundle") from exc
