from __future__ import annotations

import pytest

from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import PatchHarborError
from patchharbor.git_objects import (
    BaseTreeEntry,
    parse_base_tree_entries,
    parse_batch_blob_response,
)
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.repository_paths import RepositoryRelativePath


def _object_id(character: str, object_format: GitObjectFormat) -> GitObjectId:
    return GitObjectId(
        value=character * object_format.object_id_hex_length,
        object_format=object_format,
    )


def test_base_tree_entries_are_validated_and_sorted_by_original_path_bytes() -> None:
    first = _object_id("1", GitObjectFormat.SHA1)
    second = _object_id("2", GitObjectFormat.SHA1)
    raw = (
        f"100755 blob {second.value}\tz-last.sh".encode("ascii")
        + b"\0"
        + f"100644 blob {first.value}\ta-first.txt".encode("ascii")
        + b"\0"
    )

    entries = parse_base_tree_entries(raw, GitObjectFormat.SHA1)

    assert tuple(entry.path.original_bytes for entry in entries) == (
        b"a-first.txt",
        b"z-last.sh",
    )
    assert entries[0].object_id == first
    assert entries[0].mode == b"100644"
    assert entries[1].object_id == second
    assert entries[1].mode == b"100755"


def test_batch_blob_response_preserves_binary_bytes_and_full_sha256_ids() -> None:
    object_id = _object_id("a", GitObjectFormat.SHA256)
    entry = BaseTreeEntry(
        path=RepositoryRelativePath(b"binary.dat"),
        mode=b"100755",
        object_id=object_id,
    )
    content = b"binary\x00bytes\xff\r\n"
    response = (
        f"{object_id.value} blob {len(content)}\n".encode("ascii")
        + content
        + b"\n"
    )

    observed = parse_batch_blob_response(response, (entry,))

    assert len(observed) == 1
    assert observed[0].path == entry.path
    assert observed[0].mode == b"100755"
    assert observed[0].object_id == object_id
    assert observed[0].content == content
    assert observed[0].executable is True


@pytest.mark.parametrize(
    "response",
    [
        b"malformed\n",
        (b"2" * 40) + b" blob 1\nx\n",
        (b"1" * 40) + b" tree 1\nx\n",
        (b"1" * 40) + b" blob -1\n\n",
        (b"1" * 40) + b" blob 2\nx\n",
        (b"1" * 40) + b" blob 1\nx\ntrailing",
    ],
)
def test_batch_blob_response_rejects_protocol_mismatches(response: bytes) -> None:
    entry = BaseTreeEntry(
        path=RepositoryRelativePath(b"file.txt"),
        mode=b"100644",
        object_id=_object_id("1", GitObjectFormat.SHA1),
    )

    with pytest.raises(PatchHarborError) as captured:
        parse_batch_blob_response(response, (entry,))

    assert exit_code_for_error(captured.value) is ExitCode.RESULT_BUNDLE_ERROR


@pytest.mark.parametrize(
    "record",
    [
        (b"100644 tree " + (b"1" * 40) + b"\tfile.txt\0"),
        (b"120000 blob " + (b"1" * 40) + b"\tfile.txt\0"),
        (b"100644 blob short\tfile.txt\0"),
        (b"100644 blob " + (b"1" * 40) + b"\tfile.txt\0") * 2,
    ],
)
def test_base_tree_rejects_unsupported_or_ambiguous_entries(record: bytes) -> None:
    with pytest.raises(PatchHarborError) as captured:
        parse_base_tree_entries(record, GitObjectFormat.SHA1)

    assert exit_code_for_error(captured.value) is ExitCode.RESULT_BUNDLE_ERROR
