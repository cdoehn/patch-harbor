"""Compose fresh local handoff data for every Result Bundle publication."""

from __future__ import annotations

from datetime import datetime, timezone

from patchharbor import __version__
from patchharbor.bundle_handoff import (
    BundleHandoff,
    ENVIRONMENT_MARKER,
    ENVIRONMENT_FORMAT_VERSION,
    PATCH_FILENAME_SCHEMA,
    RESULT_FILENAME_SCHEMA,
)
from patchharbor.chat_instructions import render_chat_handoff
from patchharbor.platform.environment import capture_runtime_environment
from patchharbor.result_bundle_target import ResultBundleTarget
from patchharbor.run_report import RunReport


def create_result_handoff(report: RunReport, target: ResultBundleTarget) -> BundleHandoff:
    """Use the actually resolved repository and the revalidated output target."""
    context = report.context
    if context is None:
        raise ValueError("Result Bundle handoff requires a repository context")
    document: dict[str, object] = {
        "marker": ENVIRONMENT_MARKER,
        "format_version": ENVIRONMENT_FORMAT_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "bundle_type": "Result",
        "bundle_filename": target.final_path.name,
        "run_id": report.run_id_text,
        "repository_name": context.repository_path.value.name,
        "repository_path": str(context.repository_path.value),
        "repository_context": {
            "repo_id": str(context.repo_id),
            "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm,
        },
        "exchange_directory": str(target.exchange_directory) if target.exchange_directory is not None else None,
        "output_directory": str(target.directory),
        "bundle_suffix": target.bundle_suffix,
        "filename_schemas": {"Patch": PATCH_FILENAME_SCHEMA, "Result": RESULT_FILENAME_SCHEMA},
        "filename_timezone": "UTC",
        "runtime": {**capture_runtime_environment(), "patchharbor_version": __version__},
    }
    return render_chat_handoff(document)
