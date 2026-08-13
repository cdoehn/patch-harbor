from __future__ import annotations

import json

import pytest

from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MANIFEST_FIELDS,
    PATCH_MARKER,
    PatchManifest,
    parse_patch_manifest,
    require_manifest_object_format,
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


def _assert_package_error(payload: bytes) -> PatchHarborError:
    with pytest.raises(PatchHarborError) as captured:
        parse_patch_manifest(payload)
    assert captured.value.exit_code is ExitCode.PATCH_PACKAGE_ERROR
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
    assert manifest.base_commit.value == _VALID_DOCUMENT["base_commit"]
    assert manifest.base_commit.object_format is GitObjectFormat.SHA1
    assert PATCH_MANIFEST_FIELDS == frozenset(_VALID_DOCUMENT)


@pytest.mark.parametrize(
    ("length", "object_format"),
    [(40, GitObjectFormat.SHA1), (64, GitObjectFormat.SHA256)],
)
def test_object_id_length_is_validated_syntactically(
    length: int,
    object_format: GitObjectFormat,
) -> None:
    manifest = parse_patch_manifest(
        _payload(_with("base_commit", "a" * length))
    )

    assert manifest.base_commit.object_format is object_format


@pytest.mark.parametrize("value", [True, False, 1.0, 2])
def test_format_version_requires_the_json_integer_one(value: object) -> None:
    _assert_package_error(_payload(_with("format_version", value)))


@pytest.mark.parametrize(
    "document",
    [
        {key: value for key, value in _VALID_DOCUMENT.items() if key != "repo_id"},
        {**_VALID_DOCUMENT, "future_field": "not format 1"},
    ],
    ids=("missing", "unknown"),
)
def test_format_one_fields_are_closed(document: dict[str, object]) -> None:
    _assert_package_error(_payload(document))


@pytest.mark.parametrize(
    "payload",
    [
        b'{"marker":"patch-harbor","marker":"patch-harbor"}',
        b'{"format_version":NaN}',
    ],
    ids=("duplicate-key", "non-finite-number"),
)
def test_json_contract_rejects_ambiguous_documents(payload: bytes) -> None:
    _assert_package_error(payload)


def test_repository_object_format_must_match_the_manifest_commit() -> None:
    manifest = parse_patch_manifest(_payload())

    require_manifest_object_format(manifest, GitObjectFormat.SHA1)
    with pytest.raises(PatchHarborError) as captured:
        require_manifest_object_format(manifest, GitObjectFormat.SHA256)

    assert captured.value.exit_code is ExitCode.PATCH_PACKAGE_ERROR
    assert captured.value.error_kind is ErrorKind.PATCH_PACKAGE_ERROR
