"""Public-only transport example. Output must be a private, unwatched directory.

The caller supplies a trusted Result SHA and an independently approved host
entrypoint. This demonstrates transport, not SpecRoad's project/approval policy.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from patchharbor import api


def prepare_transport(reference: Path, *, expected_result_sha256: str,
                      trusted_entrypoint: Path, workspace: Path,
                      output_directory: Path) -> tuple[api.ResultSnapshot, api.PatchPackResult]:
    capabilities = api.integration_capabilities()
    if capabilities.contract_version != 1 or capabilities.snapshot_contract_version != 1:
        raise RuntimeError('snapshot integration contract 1 is required')
    if trusted_entrypoint.name == 'captured-project.zip':
        raise ValueError('entrypoint name collides with the project payload')
    snapshot = api.read_result_snapshot(reference, expected_sha256=expected_result_sha256)
    workspace.mkdir(exist_ok=False)
    contents = workspace / 'contents'
    contents.mkdir()
    # The nested archive is an ordinary payload. No scan of the original repo,
    # path-by-path extraction, or execution is involved.
    with ZipFile(contents / 'captured-project.zip', 'x', compression=ZIP_DEFLATED) as archive:
        for name, file in snapshot.effective.files.items():
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = int(file.mode, 8) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, file.content)
    entrypoint = trusted_entrypoint.name
    (contents / entrypoint).write_bytes(trusted_entrypoint.read_bytes())
    packed = api.pack_patch(contents, reference_bundle=reference, entrypoint=entrypoint,
                            output_directory=output_directory, modes={entrypoint: 0o755})
    if packed.reference_sha256 != snapshot.sha256:
        raise RuntimeError('reference changed between operations; do not publish the staged package')
    # Publish only the returned, verified package through the caller's own
    # authorized handoff. Authenticity and host admission are separate checks.
    return snapshot, packed
