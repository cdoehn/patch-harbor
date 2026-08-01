"""Compatibility imports for inline FILE payload handling."""

from patchharbor.payload_files import (
    MAX_PAYLOAD_BYTES,
    PAYLOAD_WARNING_BYTES,
    is_safe_payload_name,
    payload_size_warning,
    prepare_payload_files,
    write_payload_files,
)

__all__ = [
    "MAX_PAYLOAD_BYTES",
    "PAYLOAD_WARNING_BYTES",
    "is_safe_payload_name",
    "payload_size_warning",
    "prepare_payload_files",
    "write_payload_files",
]
