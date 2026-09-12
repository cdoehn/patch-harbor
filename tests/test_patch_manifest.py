from __future__ import annotations

import json

import pytest

from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import ErrorKind, PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MARKER,
    PatchManifest,
    parse_patch_manifest,
)
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM


_REPO_ID = "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d"
_VALID_DOCUMENT: dict[str, object] = {
    "marker": PATCH_MARKER,
    "format_version": PATCH_FORMAT_VERSION,
    "repo_id": _REPO_ID,
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
    "entrypoint": "run.sh",
}


def _payload(document: dict[str, object] | None = None) -> bytes:
    return json.dumps(
        _VALID_DOCUMENT if document is None else document,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _with(field: str, value: object) -> dict[str, object]:
    document = dict(_VALID_DOCUMENT)
    document[field] = value
    return document


def _without(field: str) -> dict[str, object]:
    document = dict(_VALID_DOCUMENT)
    del document[field]
    return document


def _assert_package_error(payload: bytes) -> PatchHarborError:
    with pytest.raises(PatchHarborError) as captured:
        parse_patch_manifest(payload)
    assert exit_code_for_error(captured.value) is ExitCode.PATCH_PACKAGE_ERROR
    assert captured.value.error_kind is ErrorKind.PATCH_PACKAGE_ERROR
    return captured.value


def test_parser_returns_one_typed_closed_manifest() -> None:
    manifest = parse_patch_manifest(_payload())

    assert manifest == PatchManifest(
        marker=PATCH_MARKER,
        format_version=PATCH_FORMAT_VERSION,
        repo_id=RepositoryId(_REPO_ID),
        base_commit=GitObjectId(
            str(_VALID_DOCUMENT["base_commit"]),
            GitObjectFormat.SHA1,
        ),
        state_fingerprint="a1b2c3d4e5f67890",
        fingerprint_algorithm=FINGERPRINT_ALGORITHM,
        entrypoint="run.sh",
    )


@pytest.mark.parametrize(
    ("length", "object_format"),
    [(40, GitObjectFormat.SHA1), (64, GitObjectFormat.SHA256)],
)
def test_complete_object_ids_select_their_storage_format(
    length: int,
    object_format: GitObjectFormat,
) -> None:
    manifest = parse_patch_manifest(
        _payload(_with("base_commit", "a" * length))
    )

    assert manifest.base_commit.object_format is object_format


@pytest.mark.parametrize(
    "document",
    [
        _without("repo_id"),
        {**_VALID_DOCUMENT, "future_field": "not format 1"},
        _with("marker", 1),
        _with("marker", "PATCH-HARBOR"),
        _with("format_version", True),
        _with("format_version", 2),
        _with("repo_id", "a3f9c2e1-7b4d-1a91-9d2e-5c6f8a1b2c3d"),
        _with("base_commit", "a" * 39),
        _with("base_commit", "A" * 40),
        _with("state_fingerprint", "a" * 15),
        _with("state_fingerprint", "A" * 16),
        _with("state_fingerprint", "g" * 16),
        _with("fingerprint_algorithm", "patchharbor-state-v2"),
        _with("entrypoint", ""),
        _with("entrypoint", "patch.json"),
    ],
    ids=(
        "missing-field",
        "unknown-field",
        "marker-type",
        "marker-value",
        "version-type",
        "version-value",
        "repository-id",
        "base-commit-length",
        "base-commit-case",
        "fingerprint-length",
        "fingerprint-case",
        "fingerprint-hex",
        "algorithm",
        "entrypoint-empty",
        "entrypoint-reserved",
    ),
)
def test_closed_contract_rejects_distinct_schema_violations(
    document: dict[str, object],
) -> None:
    _assert_package_error(_payload(document))


@pytest.mark.parametrize(
    "payload",
    [
        b"\xef\xbb\xbf" + _payload(),
        b"\xff",
        b"[]",
        (
            f'{{"marker":"{PATCH_MARKER}","marker":"{PATCH_MARKER}"}}'
        ).encode("utf-8"),
        b'{"marker":"patch-harbor" // comment\n}',
        _payload() + b"{}",
        b'{"marker":NaN}',
    ],
    ids=(
        "bom",
        "invalid-utf8",
        "non-object",
        "duplicate-key",
        "comment",
        "trailing-data",
        "non-finite-number",
    ),
)
def test_json_contract_rejects_ambiguous_documents(payload: bytes) -> None:
    _assert_package_error(payload)
