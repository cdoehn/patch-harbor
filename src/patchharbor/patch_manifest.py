"""Pure parsing and validation for the closed format-1 patch manifest."""

from __future__ import annotations

from dataclasses import dataclass
import json

from patchharbor.errors import patch_package_error
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM


PATCH_MANIFEST_NAME = "patch.json"
PATCH_MARKER = "patch-harbor"
PATCH_FORMAT_VERSION = 1
_PATCH_MANIFEST_FIELDS = frozenset(
    {
        "marker",
        "format_version",
        "repo_id",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "entrypoint",
    }
)


@dataclass(frozen=True)
class PatchManifest:
    """One validated closed format-1 patch manifest."""

    marker: str
    format_version: int
    repo_id: RepositoryId
    base_commit: GitObjectId
    state_fingerprint: str
    fingerprint_algorithm: str
    entrypoint: str


def _unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_json_object(payload: bytes) -> dict[str, object]:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise patch_package_error("patch.json must be UTF-8 without a BOM")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise patch_package_error("patch.json is not valid UTF-8") from exc

    try:
        document = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_non_finite_number,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise patch_package_error(
            "patch.json is not one valid JSON object"
        ) from exc

    if type(document) is not dict:
        raise patch_package_error("patch.json must contain one JSON object")
    return document


def _require_string(document: dict[str, object], field: str) -> str:
    value = document[field]
    if type(value) is not str:
        raise patch_package_error(f"patch.json {field} is invalid")
    return value


def parse_patch_manifest(payload: bytes) -> PatchManifest:
    """Parse manifest bytes without performing I/O or repository access."""
    document = _parse_json_object(payload)
    if set(document) != _PATCH_MANIFEST_FIELDS:
        raise patch_package_error(
            "patch.json must contain exactly the seven format-1 fields"
        )

    marker = _require_string(document, "marker")
    if marker != PATCH_MARKER:
        raise patch_package_error("patch.json marker is invalid")

    format_version = document["format_version"]
    if type(format_version) is not int or format_version != PATCH_FORMAT_VERSION:
        raise patch_package_error("patch.json format_version is invalid")

    repo_id_text = _require_string(document, "repo_id")
    try:
        repo_id = RepositoryId(repo_id_text)
    except ValueError as exc:
        raise patch_package_error("patch.json repo_id is invalid") from exc

    base_commit_text = _require_string(document, "base_commit")
    try:
        object_format = GitObjectFormat.for_hex_length(len(base_commit_text))
        base_commit = GitObjectId(base_commit_text, object_format)
    except ValueError as exc:
        raise patch_package_error("patch.json base_commit is invalid") from exc

    state_fingerprint = _require_string(document, "state_fingerprint")
    if (
        len(state_fingerprint) != 16
        or state_fingerprint != state_fingerprint.lower()
        or any(
            character not in "0123456789abcdef"
            for character in state_fingerprint
        )
    ):
        raise patch_package_error("patch.json state_fingerprint is invalid")

    fingerprint_algorithm = _require_string(
        document,
        "fingerprint_algorithm",
    )
    if fingerprint_algorithm != FINGERPRINT_ALGORITHM:
        raise patch_package_error(
            "patch.json fingerprint_algorithm is invalid"
        )

    entrypoint = _require_string(document, "entrypoint")
    if not entrypoint or entrypoint == PATCH_MANIFEST_NAME:
        raise patch_package_error("patch.json entrypoint is invalid")

    return PatchManifest(
        marker=marker,
        format_version=format_version,
        repo_id=repo_id,
        base_commit=base_commit,
        state_fingerprint=state_fingerprint,
        fingerprint_algorithm=fingerprint_algorithm,
        entrypoint=entrypoint,
    )


def require_manifest_object_format(
    manifest: PatchManifest,
    object_format: GitObjectFormat,
) -> None:
    """Reject a syntactically valid object ID for a different repository format."""
    if manifest.base_commit.object_format is not object_format:
        raise patch_package_error(
            "patch.json base_commit does not match the repository object format"
        )
