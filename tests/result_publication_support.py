"""Shared result publication fixtures and behavior probes."""
from __future__ import annotations

from dataclasses import replace
import json
from uuid import UUID

import pytest

from patchharbor.bundle_handoff import BundleHandoff
from patchharbor.result_bundle_publication import ResultBundlePublication, prepare_result_bundle_publication, publish_result_bundle
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor import result_verification as verification

from tests.run_report_support import successful_bundle_run_report


def _publish(publication: ResultBundlePublication, *, runtime=None, **options) -> None:
    from patchharbor.result_bundle import _context_document, _manifest_document
    from patchharbor.result_resources import runtime_payload
    final_path = publication.final_path
    report = successful_bundle_run_report(final_path.parent / "repository", final_path)
    if runtime is None:
        runtime = runtime_payload(None, reason="source_not_prepared")
    report = replace(report, warnings=runtime.warnings)
    snapshot = build_result_bundle_snapshot(base_entries=(), staged_patch=b"", unstaged_patch=b"", untracked_entries=())
    context = _context_document(report)
    environment = {
        "marker": "patch-harbor-environment", "format_version": 1, "bundle_type": "Result",
        "repository_context": {k: context[k] for k in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
        "run_id": report.run_id_text, "bundle_suffix": "",
    }
    publish_result_bundle(
        publication,
        manifest=_manifest_document(report=report, snapshot=snapshot, runtime=runtime),
        context_document=context,
        handoff=BundleHandoff(b"contract\n", json.dumps(environment).encode()),
        run_report=report,
        snapshot=snapshot,
        runtime=runtime,
        **options,
    )


@pytest.fixture
def destination(tmp_path):
    return prepare_result_bundle_publication(tmp_path / "result.zip",
        run_id=UUID("12345678-1234-4234-8234-123456789abc"))


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(verification, "sleep", calls.append)
    monkeypatch.setattr(verification, "publication_wait_budget", lambda path: 300)
    return calls
