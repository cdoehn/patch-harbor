"""Pin producer-owned runtime and template bytes before an Apply can mutate them."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

from patchharbor import __version__
from patchharbor.chat_instructions import load_chat_template
from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.json_document import serialize_json_document
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_runtime import METADATA_PATH, UNAVAILABLE_REASONS
from patchharbor.runtime_artifact import RuntimeArtifact, RuntimeProvider
from patchharbor.runtime_wheel import CONTENT_ALGORITHM

if TYPE_CHECKING:
    from patchharbor.bundle_handoff import BundleHandoff
    from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
    from patchharbor.run_report import RunReport


def _descriptor(path: str, raw: bytes) -> dict[str, object]:
    return {"path": path, "size": len(raw), "sha256": sha256(raw).hexdigest()}


@dataclass(frozen=True, slots=True)
class ResultRuntimePayload:
    """Immutable bytes; mutable JSON documents are created only at the boundary."""

    status: str
    reason: str | None
    metadata: bytes
    wheel_path: str | None = None
    wheel_bytes: bytes | None = None
    inner_content_bytes: int = 0

    def entries(self) -> tuple[tuple[str, bytes], ...]:
        result = ((METADATA_PATH, self.metadata),)
        if self.wheel_path is not None and self.wheel_bytes is not None:
            result += ((self.wheel_path, self.wheel_bytes),)
        return result

    def document(self) -> dict[str, object]:
        return {"status": self.status, "reason": self.reason,
                "metadata": _descriptor(METADATA_PATH, self.metadata),
                "wheel": None if self.wheel_path is None or self.wheel_bytes is None
                else _descriptor(self.wheel_path, self.wheel_bytes)}

    @property
    def warnings(self) -> tuple[str, ...]:
        return () if self.status == "embedded" else (f"runtime unavailable: {self.reason}",)


def runtime_payload(artifact: RuntimeArtifact | None, *, reason: str | None = None) -> ResultRuntimePayload:
    """Translate the private provider response to the closed Result-2 contract."""
    if artifact is None:
        if reason not in UNAVAILABLE_REASONS:
            raise ValueError("unsupported runtime unavailability reason")
        doc = {
            "marker": "patch-harbor-runtime", "format_version": 1,
            "status": "unavailable", "reason": reason, "distribution": "patchharbor",
            "version": __version__, "requires_python": None, "content_id": None,
            "content_id_algorithm": None, "wheel": None, "tags": None,
            "runtime_dependencies": None, "provenance": None, "capabilities": None,
        }
        return ResultRuntimePayload("unavailable", reason, serialize_json_document(doc).encode("utf-8"))
    recipe = artifact.recipe
    wheel_path = "runtime/" + recipe.wheel_name
    doc = {
        "marker": "patch-harbor-runtime", "format_version": 1,
        "status": "embedded", "reason": None, "distribution": "patchharbor",
        "version": recipe.version, "requires_python": recipe.requires_python,
        "content_id": recipe.content_id, "content_id_algorithm": CONTENT_ALGORITHM,
        "wheel": _descriptor(wheel_path, artifact.wheel_bytes), "tags": ["py3-none-any"],
        "runtime_dependencies": [],
        "provenance": {"mode": "canonical_resources", "source_commit": recipe.source_commit,
                       "recipe_format_version": 1},
        "capabilities": {"operations": ["inspect_patch", "validate_patch"],
                         "patch_formats": [1], "result_formats": [1, 2]},
    }
    # Reading central metadata does not extract or duplicate wheel payloads.
    with ZipFile(BytesIO(artifact.wheel_bytes)) as archive:
        inner_bytes = sum(info.file_size for info in archive.infolist())
    return ResultRuntimePayload("embedded", None, serialize_json_document(doc).encode("utf-8"),
                                wheel_path, artifact.wheel_bytes, inner_bytes)


@dataclass(frozen=True, slots=True)
class PinnedResultResources:
    runtime: ResultRuntimePayload
    template: str | None
    template_error: str | None = None

    def require_template(self) -> str:
        if self.template is None:
            raise result_bundle_error(self.template_error or "pinned chat template is unavailable")
        return self.template


def capture_result_resources() -> PinnedResultResources:
    """Capture once before mutation; a missing mandatory template stays a Result error."""
    provision = RuntimeProvider().capture()
    reason = {"resources_missing": "artifact_missing", "resources_invalid": "artifact_corrupt"}.get(
        provision.reason, provision.reason)
    runtime = runtime_payload(provision.artifact, reason=reason)
    try:
        template = (provision.artifact.chat_template.decode("utf-8")
                    if provision.artifact is not None else load_chat_template())
    except (PatchHarborError, UnicodeError) as exc:
        return PinnedResultResources(runtime, None, str(exc))
    return PinnedResultResources(runtime, template)


def runtime_fits(
    runtime: ResultRuntimePayload, *, manifest: dict[str, object], context_document: dict[str, object],
    handoff: BundleHandoff, run_report: RunReport, snapshot: ResultBundleSnapshot,
    execution_log: bytes | None, policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> bool:
    """Check the exact outer payload and the shared inner-byte budget before publication."""
    contents = [serialize_json_document(doc).encode("utf-8") for doc in
                (manifest, context_document, run_report.as_run_document())]
    contents.extend(raw for _, raw in handoff.entries())
    contents.extend((snapshot.staged_patch, snapshot.unstaged_patch))
    contents.extend(entry.content for entry in snapshot.base_entries)
    contents.extend(entry.content for entry in snapshot.untracked_entries)
    if execution_log is not None:
        contents.append(execution_log)
    contents.extend(raw for _, raw in runtime.entries())
    return (len(contents) <= policy.max_zip_entries
            and all(len(raw) <= policy.max_content_bytes for raw in contents)
            and sum(len(raw) for raw in contents) + runtime.inner_content_bytes <= policy.max_zip_total_bytes)
