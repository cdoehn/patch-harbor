"""Wheel RECORD serialization, separate from portable runtime recipe validation.

Used by the normal installation-wheel builder and, until RF-06, the legacy
runtime-wheel reader/writer. It owns no runtime resource or profile policy.
"""
from __future__ import annotations

import base64
import csv
import io
from typing import Iterable


def wheel_record(inventory: Iterable[tuple[str, str, int]], record_path: str) -> bytes:
    """Serialize validated (path, hex SHA-256, size) facts, excluding RECORD.

    Transport and canonical wheels share this encoding, not their inventories.
    Callers retain their own path/profile validation and resource budgets.
    """
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, digest, size in sorted(inventory):
        encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode("ascii")
        writer.writerow((name, "sha256=" + encoded, size))
    writer.writerow((record_path, "", ""))
    return record.getvalue().encode("utf-8")
