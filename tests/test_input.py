from __future__ import annotations

from io import BytesIO, StringIO
import os
from pathlib import Path
import stat

import pytest

import patchharbor.application as script_application
import patchharbor.temporary_resources as temporary_resources
from patchharbor.application import run_script_path
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import PatchHarborError
from patchharbor.output import OutputTargets
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.sources import file_input_artifact, stdin_input_artifact


def test_file_and_stdin_resolve_through_the_same_bundle_semantics(
    tmp_path: Path,
) -> None:
    script_text = "# PATCHHARBOR\n"
    script_path = tmp_path / "example.sh"
    script_path.write_bytes(script_text.encode("utf-8"))

    file_bundle = resolve_patch_bundle(file_input_artifact(script_path))

    with stdin_input_artifact(StringIO(script_text)) as stdin_artifact:
        temporary_path = stdin_artifact.path
        assert temporary_path.exists()
        stdin_bundle = resolve_patch_bundle(stdin_artifact)

    assert not temporary_path.exists()
    assert len(file_bundle.scripts) == 1
    assert len(stdin_bundle.scripts) == 1
    assert file_bundle.scripts[0].text == script_text
    assert stdin_bundle.scripts[0].text == script_text
    assert file_bundle.scripts[0].display_name == str(script_path)
    assert stdin_bundle.scripts[0].display_name == "standard input"


def test_direct_file_resolution_rejects_hard_budget(
    tmp_path: Path,
) -> None:
    source = tmp_path / "oversized-input"
    source.write_bytes(b"1234")
    policy = ResourcePolicy(
        warning_bytes=1,
        max_input_artifact_bytes=3,
        max_content_bytes=10,
        max_zip_total_bytes=20,
    )

    with pytest.raises(PatchHarborError) as raised:
        resolve_patch_bundle(file_input_artifact(source), policy=policy)

    assert exit_code_for_error(raised.value) is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)
    assert "exceeds 3 bytes" in str(raised.value)


def test_direct_file_at_hard_budget_is_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "boundary-script"
    source.write_text("# PATCHHARBOR\n", encoding="utf-8")
    size_bytes = source.stat().st_size
    policy = ResourcePolicy(
        warning_bytes=size_bytes,
        max_input_artifact_bytes=size_bytes,
        max_content_bytes=size_bytes,
        max_zip_total_bytes=size_bytes * 2,
    )
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **options: 0,
    )

    result = run_script_path(
        source,
        cwd=tmp_path,
        timeout_seconds=2,
        resource_policy=policy,
    )

    assert result == 0


def test_stdin_budget_failure_removes_secure_temporary_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(temporary_resources.tempfile, "tempdir", str(tmp_path))
    policy = ResourcePolicy(
        warning_bytes=1,
        max_input_artifact_bytes=3,
        max_content_bytes=10,
        max_zip_total_bytes=20,
    )

    with pytest.raises(PatchHarborError) as raised:
        with stdin_input_artifact(BytesIO(b"1234"), policy=policy):
            raise AssertionError("oversized input must not be yielded")

    assert exit_code_for_error(raised.value) is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)
    assert not tuple(tmp_path.glob("patchharbor-input-*"))


def test_stdin_artifact_uses_unique_user_only_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(temporary_resources.tempfile, "tempdir", str(tmp_path))

    with stdin_input_artifact(BytesIO(b"# PATCHHARBOR\n")) as first:
        first_path = first.path
        first_mode = stat.S_IMODE(first_path.stat().st_mode)
        with stdin_input_artifact(BytesIO(b"# PATCHHARBOR\n")) as second:
            second_path = second.path
            assert first_path != second_path
            if os.name != "nt":
                assert first_mode == 0o600
                assert stat.S_IMODE(second_path.stat().st_mode) == 0o600

    assert not first_path.exists()
    assert not second_path.exists()
    assert not tuple(tmp_path.glob("patchharbor-input-*"))


def test_direct_reader_rechecks_budget_after_artifact_creation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "growing-input"
    source.write_bytes(b"123")
    artifact = file_input_artifact(source)
    source.write_bytes(b"123456")
    policy = ResourcePolicy(
        warning_bytes=1,
        max_input_artifact_bytes=5,
        max_content_bytes=10,
        max_zip_total_bytes=20,
    )

    with pytest.raises(PatchHarborError) as raised:
        resolve_patch_bundle(artifact, policy=policy)

    assert exit_code_for_error(raised.value) is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)


def test_large_source_warning_reaches_plain_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "large-script"
    source.write_bytes(b"# PATCHHARBOR\n")
    source_size = source.stat().st_size
    warning_output = StringIO()
    policy = ResourcePolicy(
        warning_bytes=3,
        max_input_artifact_bytes=100,
        max_content_bytes=100,
        max_zip_total_bytes=200,
    )
    monkeypatch.setattr(
        script_application,
        "execute_script_text",
        lambda script_text, **options: 0,
    )

    result = run_script_path(
        source,
        cwd=tmp_path,
        timeout_seconds=2,
        output=OutputTargets(
            visible_text_stream=StringIO(),
            warning_text_stream=warning_output,
        ),
        resource_policy=policy,
    )

    assert result == 0
    assert warning_output.getvalue() == (
        "patchharbor: warning: input artifact is large "
        f"({source_size} bytes)\n"
    )
