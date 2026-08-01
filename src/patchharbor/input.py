"""Compatibility imports for the input API split in step 3.a.R."""

from patchharbor.application import (
    discover_directory_candidates,
    run_input_artifact,
    run_script_path,
)
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    select_directory_candidate,
    stdin_input_artifact,
)

__all__ = [
    "DirectoryCandidate",
    "discover_directory_candidates",
    "file_input_artifact",
    "resolve_patch_bundle",
    "run_input_artifact",
    "run_script_path",
    "select_directory_candidate",
    "stdin_input_artifact",
]
