"""Shared patch inspection fixtures and behavior probes."""
from __future__ import annotations

import json
from pathlib import Path
import stat
from zipfile import ZipFile, ZipInfo


MANIFEST = {
    "marker": "patch-harbor", "format_version": 1,
    "repo_id": "01234567-89ab-4cde-8fab-0123456789ab",
    "base_commit": "12" * 20, "state_fingerprint": "0123456789abcdef",
    "fingerprint_algorithm": "patchharbor-state-v1", "entrypoint": "run.sh",
}

SCRIPT = (b"#!/usr/bin/env bash\n# PATCHHARBOR\n"
          b"# PATCHHARBOR MESSAGE Notice START\n# Facts only\n# PATCHHARBOR MESSAGE Notice END\n"
          b"printf executed > SHOULD_NOT_EXIST\n")


def write_package(path: Path, *, changes: dict[str, bytes] | None = None,
                  handoff: bool = False) -> dict[str, bytes]:
    entries = {"patch.json": json.dumps(MANIFEST).encode(), "run.sh": SCRIPT,
               "docs/data.bin": b"\x00\xff\r\nbyte-exact"}
    if handoff:
        environment = {
            "marker": "patch-harbor-environment", "format_version": 1, "bundle_type": "Patch",
            "repository_context": {k: MANIFEST[k] for k in
                                   ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
        }
        entries.update({"PATCHHARBOR_META/CHAT_INSTRUCTIONS.md": b"# Passive\n",
                        "PATCHHARBOR_META/environment.json": json.dumps(environment).encode()})
    entries.update(changes or {})
    with ZipFile(path, "w") as archive:
        directory = ZipInfo("docs/")
        directory.create_system = 3
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16
        archive.writestr(directory, b"")
        for name, data in entries.items():
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name == "run.sh" else 0o644)) << 16
            archive.writestr(info, data)
    return entries
