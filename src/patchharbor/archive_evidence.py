"""Conservative archival/recovery policy over shared, integrity-checked Result facts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.exchange_state import ExchangePatchSelection
from patchharbor.models import BundlePayload, GitObjectId
from patchharbor.patch_package import resolve_patch_payloads
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import CLEAN_FINGERPRINT, parse_result_payloads, read_result_or_patch_payloads
from patchharbor.run_report import PrimaryResultKind


@dataclass(frozen=True)
class ApplyReceipt:
    """An executed patch's full binding; trust also requires the local ZIP digest."""

    patch_sha256: str
    run_id: str
    expected: ExchangePatchSelection
    completed_commit: GitObjectId


@dataclass(frozen=True)
class ArchiveEvidence:
    """Validated manifest binding and, for clean results, the full blob inventory."""

    kind: str
    selection: ExchangePatchSelection
    base_entries: tuple[tuple[str, str, str], ...] = ()  # path, mode, object ID
    receipt: ApplyReceipt | None = None


def _result_evidence(payloads: tuple[BundlePayload, ...]) -> ArchiveEvidence:
    try:
        facts = parse_result_payloads(payloads)
    except OverflowError as exc:
        # The reference API maps this numeric input failure to SOURCE_ERROR;
        # archival/recovery consumers retain their conservative KEEP boundary.
        raise ValueError("invalid numeric Result metadata") from exc
    context = facts.context
    # A valid dirty/error/dry-run reference is never an archival success proof.
    # Warnings and legacy missing expected bindings retain the existing KEEP policy.
    if (context.dirty or facts.dry_run or facts.warnings
        or facts.primary_result.kind is not PrimaryResultKind.SUCCESS
        or (facts.operation == "apply") != (facts.expected is not None)):
        raise ValueError("result is not a clean, completed archival success")
    selection = ExchangePatchSelection(context.repo_id, context.base_commit,
                                       context.state_fingerprint, context.fingerprint_algorithm)
    receipt = None
    if facts.completed_commit is not None:
        # The reader has already validated the entire receipt and actual context.
        assert facts.patch_sha256 is not None and facts.expected is not None
        receipt = ApplyReceipt(facts.patch_sha256, facts.run_id, facts.expected, facts.completed_commit)
    return ArchiveEvidence("result_bundle", selection, facts.base_entries, receipt)


def parse_archive_evidence(content: bytes, path: Path) -> ArchiveEvidence:
    """Validate complete bytes; errors mean 'keep', never an archival decision."""
    payloads = read_result_or_patch_payloads(content)
    files = {item.relative_path: item.content for item in payloads}
    if "manifest.json" in files and "patch.json" in files:
        raise ValueError("ambiguous bundle kind")
    if "manifest.json" in files:
        return _result_evidence(payloads)
    package = resolve_patch_payloads(payloads, package_path=path, resource_policy=DEFAULT_RESOURCE_POLICY)
    return ArchiveEvidence("patch_package", ExchangePatchSelection.from_manifest(package.manifest))
