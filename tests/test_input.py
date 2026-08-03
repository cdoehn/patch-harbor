from __future__ import annotations

from io import BytesIO, StringIO
import os
from pathlib import Path
import stat

import pytest

import patchharbor.application as script_application
import patchharbor.sources as script_sources
from patchharbor.application import run_script_path
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.output import OutputTargets
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.sources import file_input_artifact, stdin_input_artifact


def test_file_and_stdin_resolve_through_the_same_bundle_semantics(
    tmp_path: Path,
) -> None:
    script_text = "# PATCHHARBOR\n"
    script_path = tmp_path / "example.sh"
    script_path.write_text(script_text, encoding="utf-8")

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


def test_file_input_artifact_rejects_hard_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        file_input_artifact(source, policy=policy)

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)
    assert "exceeds 3 bytes" in str(raised.value)


def test_stdin_budget_failure_removes_secure_temporary_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_paths: list[Path] = []
    real_mkstemp = script_sources.tempfile.mkstemp

    def recording_mkstemp(*, prefix: str) -> tuple[int, str]:
        descriptor, raw_path = real_mkstemp(prefix=prefix, dir=tmp_path)
        created_paths.append(Path(raw_path))
        return descriptor, raw_path

    monkeypatch.setattr(script_sources.tempfile, "mkstemp", recording_mkstemp)
    policy = ResourcePolicy(
        warning_bytes=1,
        max_input_artifact_bytes=3,
        max_content_bytes=10,
        max_zip_total_bytes=20,
    )

    with pytest.raises(PatchHarborError) as raised:
        with stdin_input_artifact(BytesIO(b"1234"), policy=policy):
            raise AssertionError("oversized input must not be yielded")

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)
    assert len(created_paths) == 1
    assert not created_paths[0].exists()


def test_stdin_artifact_uses_unique_user_only_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_mkstemp = script_sources.tempfile.mkstemp

    def local_mkstemp(*, prefix: str) -> tuple[int, str]:
        return real_mkstemp(prefix=prefix, dir=tmp_path)

    monkeypatch.setattr(script_sources.tempfile, "mkstemp", local_mkstemp)

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


def test_direct_reader_rechecks_budget_after_artifact_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    assert raised.value.exit_code is ExitCode.SOURCE_ERROR
    assert "resource limit exceeded" in str(raised.value)


def test_large_source_warning_reaches_plain_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "large-script"
    source.write_text("# PATCHHARBOR\n", encoding="utf-8")
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
        selection_input=StringIO(),
        selection_output=StringIO(),
        output=OutputTargets(
            visible_text_stream=StringIO(),
            warning_text_stream=warning_output,
        ),
        resource_policy=policy,
    )

    assert result == 0
    assert warning_output.getvalue() == (
        "patchharbor: warning: input artifact is large (14 bytes)\n"
    )
