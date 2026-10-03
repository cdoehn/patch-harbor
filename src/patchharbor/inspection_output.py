"""Pure version-2 JSON projections of checked immutable package facts."""
from __future__ import annotations

from patchharbor.patch_inspection import PatchInspection, PatchValidationResult
from patchharbor.context_output import context_json_result


def inspection_json_result(info: PatchInspection) -> dict[str, object]:
    manifest = info.manifest
    return {
        "package_sha256": info.package_sha256,
        "package_size": info.package_size,
        "manifest": {
            "marker": manifest.marker, "format_version": manifest.format_version,
            "repo_id": str(manifest.repo_id), "base_commit": str(manifest.base_commit),
            "state_fingerprint": manifest.state_fingerprint,
            "fingerprint_algorithm": manifest.fingerprint_algorithm,
            "entrypoint": manifest.entrypoint,
        },
        "entrypoint": info.entrypoint,
        "entries": [
            {"path": entry.path, "role": entry.role.value, "size": entry.size,
             "sha256": entry.sha256, "unix_mode": entry.unix_mode}
            for entry in info.entries
        ],
        "messages": [{"name": message.name, "text": message.text} for message in info.messages],
        "warnings": list(info.warnings),
    }


def validation_json_result(report: PatchValidationResult) -> dict[str, object]:
    return {
        "inspection": inspection_json_result(report.inspection), "scope": report.scope.value,
        "binding_matches": report.binding_matches,
        "context": None if report.context is None else context_json_result(report.context),
        "reference_sha256": report.reference_sha256,
        "checked_at": report.checked_at.isoformat().replace("+00:00", "Z"),
        "not_checked": list(report.not_checked),
    }
