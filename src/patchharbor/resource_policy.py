"""Central immutable resource limits for one PatchHarbor runner request."""

from __future__ import annotations

from dataclasses import dataclass


_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    """Small coherent set of limits used by every input path."""

    warning_bytes: int = 10 * _MIB
    max_input_artifact_bytes: int = 256 * _MIB
    max_content_bytes: int = 256 * _MIB
    max_zip_total_bytes: int = 512 * _MIB
    max_zip_entries: int = 1_000
    read_chunk_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        values = {
            "warning_bytes": self.warning_bytes,
            "max_input_artifact_bytes": self.max_input_artifact_bytes,
            "max_content_bytes": self.max_content_bytes,
            "max_zip_total_bytes": self.max_zip_total_bytes,
            "max_zip_entries": self.max_zip_entries,
            "read_chunk_bytes": self.read_chunk_bytes,
        }
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.warning_bytes > self.max_input_artifact_bytes:
            raise ValueError(
                "warning_bytes must not exceed max_input_artifact_bytes"
            )
        if self.warning_bytes > self.max_content_bytes:
            raise ValueError(
                "warning_bytes must not exceed max_content_bytes"
            )

    def large_content_warning(
        self,
        label: str,
        size_bytes: int,
    ) -> str | None:
        """Return one stable warning when a valid content item is large."""
        if size_bytes > self.warning_bytes:
            return f"{label} is large ({size_bytes} bytes)"
        return None


DEFAULT_RESOURCE_POLICY = ResourcePolicy()
