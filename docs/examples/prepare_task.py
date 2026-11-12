"""Prepare one Task from a trusted Result; do not execute or publish it."""
from pathlib import Path

from patchharbor import api


def prepare_task(contents: Path, *, reference: Path, expected_result_sha256: str,
                 entrypoint: str, output_directory: Path) -> api.TaskPackResult:
    snapshot = api.read_result_snapshot(reference, expected_sha256=expected_result_sha256)
    prepared = api.pack_task(contents, reference_bundle=reference,
                            entrypoint=entrypoint, output_directory=output_directory)
    if prepared.reference_sha256 != snapshot.sha256:
        raise ValueError('reference changed while preparing the task; do not transfer it')
    checked = api.validate_task(prepared.path, reference_bundle=reference)
    if not checked.binding_matches or checked.inspection.package_sha256 != prepared.package_sha256:
        raise ValueError('prepared task changed; do not transfer it')
    return prepared
