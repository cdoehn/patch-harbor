from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import ErrorKind, PatchHarborError
from patchharbor.git_patches import capture_change_patches
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryPath


def test_patch_capture_failure_is_a_result_bundle_error(tmp_path: Path) -> None:
    repository = RepositoryPath(tmp_path.resolve())
    base_commit = GitObjectId(
        value="0" * GitObjectFormat.SHA1.object_id_hex_length,
        object_format=GitObjectFormat.SHA1,
    )

    with pytest.raises(PatchHarborError) as captured:
        capture_change_patches(repository, base_commit)

    assert exit_code_for_error(captured.value) is ExitCode.RESULT_BUNDLE_ERROR
    assert captured.value.error_kind is ErrorKind.RESULT_BUNDLE_ERROR
