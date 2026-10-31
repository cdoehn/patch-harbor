"""Public-only host integration: authorize boundaries before source-safe export."""
from hashlib import sha256
from pathlib import Path

from patchharbor import api


def export_reference(repository, *, output_directory, authorize):
    """Return (plan, bundle, snapshot); never register, repair or use a fallback.

    authorize receives the immutable public SafeExportPlan and must return True
    only after the caller's own scope/closure/approval policy accepts it.
    """
    capability = getattr(api, 'integration_capabilities', None)
    if not callable(capability):
        raise RuntimeError('source-safe reference capability is unavailable')
    version = getattr(capability(), 'safe_reference_contract_version', None)
    if type(version) is not int or version != 1:
        raise RuntimeError('source-safe reference contract 1 is required')
    if not callable(authorize):
        raise TypeError('authorize must be callable')
    context = api.context(repository, capture_mode='safe')
    plan = api.prepare_reference_export(repository, output_directory=output_directory,
                                        expected_context=context)
    if authorize(plan) is not True:
        raise PermissionError('safe reference operating scope was not authorized')
    bundle = api.bundle(repository, capture_mode='safe', export_plan=plan)
    expected_sha256 = sha256(Path(bundle.path).read_bytes()).hexdigest()
    snapshot = api.read_result_snapshot(bundle.path, expected_sha256=expected_sha256)
    fields = ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')
    if any(getattr(snapshot.context, name) != getattr(context, name) for name in fields):
        raise RuntimeError('published reference differs from the approved source')
    return plan, bundle, snapshot
