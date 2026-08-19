"""Minimal Result Bundle marker check used only to prevent watcher loops."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile


_RESULT_BUNDLE_MARKER = "patch-harbor-result-bundle"
_MAX_RESULT_MANIFEST_BYTES = 1024 * 1024


def is_result_bundle_for_loop_prevention(path: Path) -> bool:
    """Recognize only the reserved marker, without parsing a package contract."""
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            matching = [
                info
                for info in archive.infolist()
                if info.filename == "manifest.json" and not info.is_dir()
            ]
            if len(matching) != 1:
                return False
            manifest = matching[0]
            if manifest.file_size > _MAX_RESULT_MANIFEST_BYTES:
                return False
            with archive.open(manifest, mode="r") as stream:
                payload = stream.read(_MAX_RESULT_MANIFEST_BYTES + 1)
            if len(payload) > _MAX_RESULT_MANIFEST_BYTES:
                return False
        document = json.loads(payload.decode("utf-8"))
    except (
        OSError,
        RuntimeError,
        NotImplementedError,
        UnicodeDecodeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ):
        return False
    return (
        isinstance(document, dict)
        and document.get("marker") == _RESULT_BUNDLE_MARKER
    )
