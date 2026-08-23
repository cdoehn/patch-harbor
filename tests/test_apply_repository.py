from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
import errno
from io import StringIO
import json
from pathlib import Path
import tempfile
import zipfile

import pytest

import patchharbor.application as application_module
import patchharbor.apply_mutation as apply_mutation_module
import patchharbor.apply_preflight as apply_preflight_module
import patchharbor.payload_files as payload_files_module
import patchharbor.result_bundle_publication as publication_module
from patchharbor.cli import main as cli_main
from patchharbor.application import (
    apply_patch_package,
    dry_run_patch_package,
    preflight_patch_package_repository,
    register_repository,
)
from patchharbor.apply_mutation import ApplyMutationGate
from patchharbor.apply_repository import safely_resolved_repository
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    unsupported_repository_state_error,
)
from patchharbor.execution import ScriptExecutionResult
from patchharbor.interpreters import InterpreterSpec, ResolvedInterpreter
from patchharbor.models import (
    BundlePayload,
    RepositoryContext,
    RepositoryPath,
    RepositorySnapshot,
)
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MARKER,
    PatchManifest,
)
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.run_report import (
    PrimaryResultKind,
    ResultBundleStatus,
    RunSession,
)
from tests.platform_support import native_script, project_environment
from tests.registration_support import (
    create_repository,
    git,
    probe_registry_lock,
    probe_repository_lock,
    set_isolated_user_environment,
)


pytestmark = pytest.mark.e2e


def _manifest(context: RepositoryContext) -> PatchManifest:
    return PatchManifest(
        marker=PATCH_MARKER,
        format_version=PATCH_FORMAT_VERSION,
        repo_id=context.repo_id,
        base_commit=context.base_commit,
        state_fingerprint=context.state_fingerprint,
        fingerprint_algorithm=context.fingerprint_algorithm,
        entrypoint="run.sh",
    )


def _package(
    manifest: PatchManifest,
    *,
    entrypoint: bytes = b"# PATCHHARBOR\n",
    payloads: tuple[BundlePayload, ...] = (),
) -> ValidatedPatchPackage:
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=BundlePayload(
            relative_path="run.sh",
            content=entrypoint,
        ),
        payloads=payloads,
    )


def _write_package_zip(
    path: Path,
    context: RepositoryContext,
    *,
    entrypoint: bytes,
) -> None:
    manifest = _manifest(context)
    document = {
        "marker": manifest.marker,
        "format_version": manifest.format_version,
        "repo_id": str(manifest.repo_id),
        "base_commit": str(manifest.base_commit),
        "state_fingerprint": manifest.state_fingerprint,
        "fingerprint_algorithm": manifest.fingerprint_algorithm,
        "entrypoint": manifest.entrypoint,
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                document,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(manifest.entrypoint, entrypoint)


def _set_private_temp(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
) -> None:
    path.mkdir()
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(path))
    monkeypatch.setattr(tempfile, "tempdir", None)


def _complete_preflight(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
) -> None:
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
    ):
        pass


class _RecordingApplyPresentation:
    def __init__(self) -> None:
        self.repository: dict[str, object] | None = None
        self.script: dict[str, object] | None = None

    def update_repository(self, **values: object) -> None:
        self.repository = values

    def begin_script(self, **values: object) -> None:
        self.script = values


def test_safe_resolution_owns_output_reservation_and_repository_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    output_directory = tmp_path / "results"
    temporary_path: Path

    with safely_resolved_repository(
        _manifest(context),
        session=RunSession.start(),
        output_directory=output_directory,
    ) as resolved:
        temporary_path = resolved.result_publication.temporary_path
        assert resolved.repository == context.repository_path
        assert resolved.repo_id == context.repo_id
        assert resolved.context == context
        assert resolved.registry_lock_path.is_absolute()
        assert resolved.repository_lock_path.is_absolute()
        assert resolved.result_target.directory == output_directory.resolve()
        assert temporary_path.is_file()
        assert temporary_path.stat().st_size > 0
        assert not resolved.result_publication.final_path.exists()
        assert probe_registry_lock(environment) == 0
        assert probe_repository_lock(str(context.repo_id), environment) == int(
            ExitCode.REPOSITORY_BUSY
        )

    assert not temporary_path.exists()
    assert probe_repository_lock(str(context.repo_id), environment) == 0


def test_safe_resolution_releases_reservation_and_lock_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    temporary_path: Path

    with pytest.raises(RuntimeError):
        with safely_resolved_repository(
            _manifest(context),
            session=RunSession.start(),
            output_directory=tmp_path / "results",
        ) as resolved:
            temporary_path = resolved.result_publication.temporary_path
            raise RuntimeError("simulated later preflight failure")

    assert not temporary_path.exists()
    assert probe_repository_lock(str(context.repo_id), environment) == 0


def test_state_mismatch_publishes_while_repository_lock_is_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    manifest = replace(
        _manifest(context),
        state_fingerprint=(
            "0" + context.state_fingerprint[1:]
            if context.state_fingerprint[0] != "0"
            else "1" + context.state_fingerprint[1:]
        ),
    )
    observed_lock_codes: list[int] = []
    original_replace = publication_module.replace_path

    def replace_while_observing_lock(source: Path, target: Path) -> None:
        observed_lock_codes.append(
            probe_repository_lock(str(context.repo_id), environment)
        )
        original_replace(source, target)

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        replace_while_observing_lock,
    )
    output_directory = tmp_path / "results"

    with pytest.raises(PatchHarborError) as captured:
        _complete_preflight(
            _package(manifest),
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.STATE_MISMATCH
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(str(context.repo_id), environment) == 0
    bundles = tuple(output_directory.glob("patchharbor_result_*.zip"))
    assert len(bundles) == 1
    assert not tuple(output_directory.glob(".*.tmp"))


def test_dry_run_publishes_before_releasing_repository_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    observed_lock_codes: list[int] = []
    original_replace = publication_module.replace_path

    def replace_while_observing_lock(source: Path, target: Path) -> None:
        observed_lock_codes.append(
            probe_repository_lock(str(context.repo_id), environment)
        )
        original_replace(source, target)

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        replace_while_observing_lock,
    )

    report = dry_run_patch_package(
        _package(_manifest(context)),
        output_directory=tmp_path / "results",
    )

    assert report.primary_result.success is True
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(str(context.repo_id), environment) == 0


def test_successful_primary_outcome_becomes_exit_eleven_when_bundle_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)

    def fail_publication(_source: Path, _target: Path) -> None:
        raise OSError("publication failed")

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        fail_publication,
    )

    with pytest.raises(PatchHarborError) as captured:
        dry_run_patch_package(
            _package(_manifest(context)),
            output_directory=tmp_path / "results",
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.RESULT_BUNDLE_ERROR
    assert report is not None
    assert report.primary_result.kind is PrimaryResultKind.DRY_RUN_SUCCESS
    assert report.result_bundle.status is ResultBundleStatus.FAILED
    assert report.process_exit_code == int(ExitCode.RESULT_BUNDLE_ERROR)


def test_primary_failure_keeps_its_exit_code_when_bundle_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)

    def fail_publication(_source: Path, _target: Path) -> None:
        raise OSError("publication failed")

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        fail_publication,
    )

    with pytest.raises(PatchHarborError) as captured:
        dry_run_patch_package(
            _package(
                _manifest(context),
                entrypoint=b"#!/usr/bin/env python3\n# PATCHHARBOR\n",
            ),
            output_directory=tmp_path / "results",
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert report is not None
    assert report.primary_result.kind is PrimaryResultKind.VALIDATION_ERROR
    assert report.result_bundle.status is ResultBundleStatus.FAILED
    assert report.process_exit_code == int(ExitCode.INTERPRETER_ERROR)


@pytest.mark.parametrize(
    ("scenario", "expected_exit", "expected_kind", "raises_error"),
    (
        (
            "success",
            int(ExitCode.RESULT_BUNDLE_ERROR),
            PrimaryResultKind.SUCCESS,
            True,
        ),
        ("entrypoint-exit", 23, PrimaryResultKind.ENTRYPOINT_EXIT, False),
        ("timeout", int(ExitCode.TIMEOUT), PrimaryResultKind.TIMEOUT, True),
        (
            "interrupted",
            int(ExitCode.INTERRUPTED),
            PrimaryResultKind.INTERRUPTED,
            True,
        ),
    ),
)
def test_apply_result_matrix_preserves_emergency_execution_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_exit: int,
    expected_kind: PrimaryResultKind,
    raises_error: bool,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _set_private_temp(monkeypatch, tmp_path / "system-temp")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    output_directory = tmp_path / "results"
    execution_output = f"matrix-{scenario}\n".encode("ascii")

    if scenario == "success":
        execution = ScriptExecutionResult.exited(0, execution_output)
    elif scenario == "entrypoint-exit":
        execution = ScriptExecutionResult.exited(23, execution_output)
    elif scenario == "timeout":
        execution = ScriptExecutionResult.failed(
            PatchHarborError("timed out", ExitCode.TIMEOUT),
            entrypoint_started=True,
            output=execution_output,
        )
    else:
        execution = ScriptExecutionResult.failed(
            PatchHarborError("interrupted", ExitCode.INTERRUPTED),
            entrypoint_started=True,
            output=execution_output,
        )

    monkeypatch.setattr(
        application_module,
        "execute_prepared_script_with_log",
        lambda *_args, **_kwargs: execution,
    )

    def fail_publication(_source: Path, _target: Path) -> None:
        raise OSError("publication failed")

    monkeypatch.setattr(publication_module, "replace_path", fail_publication)

    captured_error: PatchHarborError | None = None
    try:
        report = apply_patch_package(
            _package(_manifest(context)),
            output_directory=output_directory,
        )
    except PatchHarborError as error:
        captured_error = error
        report = error.run_report
        assert report is not None

    assert (captured_error is not None) is raises_error
    if captured_error is not None:
        assert int(captured_error.exit_code) == expected_exit
    assert report.primary_result.kind is expected_kind
    assert report.process_exit_code == expected_exit
    assert report.result_bundle.status is ResultBundleStatus.FAILED
    emergency_path = report.result_bundle.emergency_diagnostics_path
    assert emergency_path is not None
    assert emergency_path.is_dir()
    assert (emergency_path / "execution.log").read_bytes() == execution_output
    run_document = json.loads(
        (emergency_path / "run.json").read_text(encoding="utf-8")
    )
    assert run_document["primary_result"]["kind"] == expected_kind.value
    assert run_document["result_bundle"]["status"] == "failed"
    assert run_document["process_exit_code"] == expected_exit
    assert not tuple(output_directory.glob("patchharbor_result_*.zip"))
    assert not tuple(output_directory.glob(".*.tmp"))


@pytest.mark.parametrize(
    "scenario",
    ("success", "entrypoint-exit", "timeout", "interrupted"),
)
def test_apply_removes_private_resources_after_every_process_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "system-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)

    if scenario == "success":
        execution = ScriptExecutionResult.exited(0, b"success\n")
    elif scenario == "entrypoint-exit":
        execution = ScriptExecutionResult.exited(23, b"failed\n")
    elif scenario == "timeout":
        execution = ScriptExecutionResult.failed(
            PatchHarborError("timed out", ExitCode.TIMEOUT),
            entrypoint_started=True,
            output=b"timeout\n",
        )
    else:
        execution = ScriptExecutionResult.failed(
            PatchHarborError("interrupted", ExitCode.INTERRUPTED),
            entrypoint_started=True,
            output=b"interrupted\n",
        )

    monkeypatch.setattr(
        application_module,
        "execute_prepared_script_with_log",
        lambda *_args, **_kwargs: execution,
    )

    try:
        apply_patch_package(
            _package(_manifest(context)),
            output_directory=tmp_path / "results",
        )
    except PatchHarborError as error:
        assert scenario in {"timeout", "interrupted"}
        assert error.exit_code in {ExitCode.TIMEOUT, ExitCode.INTERRUPTED}

    assert tuple(private_temp.iterdir()) == ()


def test_apply_json_is_closed_and_preserves_emergency_execution_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _set_private_temp(monkeypatch, tmp_path / "system-temp")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    package = tmp_path / "failure.zip"
    raw_marker = "raw-entrypoint-output-for-json"
    _write_package_zip(
        package,
        context,
        entrypoint=native_script(
            f"printf '{raw_marker}\n'\nexit 23",
            f"[Console]::Out.WriteLine('{raw_marker}')\nexit 23",
        ).encode("utf-8"),
    )
    output_directory = tmp_path / "results"

    def fail_publication(_source: Path, _target: Path) -> None:
        raise OSError("publication failed")

    monkeypatch.setattr(publication_module, "replace_path", fail_publication)
    stdout = StringIO()
    exit_code = cli_main(
        [
            "apply",
            "--json",
            "--output-dir",
            str(output_directory),
            str(package),
        ],
        stdin=StringIO(),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 23
    assert raw_marker not in stdout.getvalue()
    envelope = json.loads(stdout.getvalue())
    assert set(envelope) == {
        "output_version",
        "command",
        "success",
        "result",
        "error",
        "process_exit_code",
    }
    assert envelope["error"] is None
    assert envelope["process_exit_code"] == 23
    result = envelope["result"]
    assert set(result) == {
        "run_id",
        "repository_resolved",
        "repo_id",
        "repository_path",
        "primary_result",
        "result_bundle",
    }
    assert set(result["primary_result"]) == {
        "kind",
        "entrypoint_started",
        "entrypoint_exit_code",
        "timed_out",
        "interrupted",
        "patchharbor_error_code",
    }
    assert result["primary_result"]["kind"] == "entrypoint_exit"
    assert set(result["result_bundle"]) == {
        "attempted",
        "status",
        "path",
        "emergency_diagnostics_path",
    }
    assert result["result_bundle"]["status"] == "failed"
    assert result["result_bundle"]["path"] is None
    emergency_path = Path(
        result["result_bundle"]["emergency_diagnostics_path"]
    )
    assert raw_marker.encode("utf-8") in (
        emergency_path / "execution.log"
    ).read_bytes()
    assert not tuple(output_directory.glob("patchharbor_result_*.zip"))
    assert not tuple(output_directory.glob(".*.tmp"))


def test_preflight_failure_bundles_before_releasing_repository_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    observed_lock_codes: list[int] = []
    original_replace = publication_module.replace_path

    def replace_while_observing_lock(source: Path, target: Path) -> None:
        observed_lock_codes.append(
            probe_repository_lock(str(context.repo_id), environment)
        )
        original_replace(source, target)

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        replace_while_observing_lock,
    )

    with pytest.raises(PatchHarborError) as captured:
        dry_run_patch_package(
            _package(
                _manifest(context),
                entrypoint=b"#!/usr/bin/env python3\n# PATCHHARBOR\n",
            ),
            output_directory=tmp_path / "results",
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert report is not None
    assert report.result_bundle.path is not None
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(str(context.repo_id), environment) == 0


@pytest.mark.parametrize("change_kind", ("base_commit", "fingerprint"))
def test_repository_change_after_preflight_is_bundled_without_payload_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change_kind: str,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    output_directory = tmp_path / "results"
    package = _package(
        _manifest(context),
        entrypoint=native_script(
            "printf executed > executed.txt",
            "[System.IO.File]::WriteAllText('executed.txt', 'executed')",
        ).encode("utf-8"),
        payloads=(
            BundlePayload(
                relative_path="files/payload.bin",
                content=b"payload",
            ),
        ),
    )
    original_capture = (
        apply_mutation_module.capture_consistent_repository_snapshot
    )
    capture_count = 0

    def change_repository_before_second_capture(
        captured_repository: RepositoryPath,
    ) -> RepositorySnapshot:
        nonlocal capture_count
        capture_count += 1
        if capture_count == 1:
            (repository / "external.txt").write_bytes(b"external change")
            if change_kind == "base_commit":
                git(repository, "add", "external.txt")
                git(repository, "commit", "--quiet", "-m", "external change")
        return original_capture(captured_repository)

    monkeypatch.setattr(
        apply_mutation_module,
        "capture_consistent_repository_snapshot",
        change_repository_before_second_capture,
    )

    with pytest.raises(PatchHarborError) as captured:
        apply_patch_package(package, output_directory=output_directory)

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.STATE_MISMATCH
    assert report is not None
    assert report.context is not None
    if change_kind == "base_commit":
        assert report.context.base_commit != context.base_commit
        assert report.context.state_fingerprint == context.state_fingerprint
    else:
        assert report.context.base_commit == context.base_commit
        assert report.context.state_fingerprint != context.state_fingerprint
    assert report.primary_result.entrypoint_started is False
    assert report.result_bundle.status is ResultBundleStatus.CREATED
    assert capture_count == 1
    assert (repository / "external.txt").read_bytes() == b"external change"
    assert not (repository / "files" / "payload.bin").exists()
    assert not (repository / "executed.txt").exists()
    assert not tuple(repository.rglob(".patchharbor-*.tmp"))

    bundle_path = report.result_bundle.path
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        actual_context = json.loads(archive.read("context.json"))
        bundled_external = archive.read(
            "base/external.txt"
            if change_kind == "base_commit"
            else "untracked/external.txt"
        )

    assert bundled_external == b"external change"
    assert actual_context["base_commit"] == str(report.context.base_commit)
    assert actual_context["state_fingerprint"] == report.context.state_fingerprint
    assert "untracked/files/payload.bin" not in names
    assert "logs/execution.log" not in names


def test_second_capture_failure_is_bundled_before_releasing_repository_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    environment = project_environment()
    observed_lock_codes: list[int] = []
    original_replace = publication_module.replace_path

    def fail_second_capture(_repository: object) -> object:
        raise unsupported_repository_state_error("simulated unsupported state")

    def replace_while_observing_lock(source: Path, target: Path) -> None:
        observed_lock_codes.append(
            probe_repository_lock(str(context.repo_id), environment)
        )
        original_replace(source, target)

    monkeypatch.setattr(
        apply_mutation_module,
        "capture_consistent_repository_snapshot",
        fail_second_capture,
    )
    monkeypatch.setattr(
        publication_module,
        "replace_path",
        replace_while_observing_lock,
    )

    with pytest.raises(PatchHarborError) as captured:
        apply_patch_package(
            _package(_manifest(context)),
            output_directory=tmp_path / "results",
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    assert report is not None
    assert report.result_bundle.status is ResultBundleStatus.CREATED
    assert report.primary_result.entrypoint_started is False
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(str(context.repo_id), environment) == 0


def test_parent_replaced_after_second_context_is_rejected_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    parent = repository / "assets"
    parent.mkdir()
    context = register_repository(repository)
    output_directory = tmp_path / "results"
    package = _package(
        _manifest(context),
        entrypoint=native_script(
            "printf executed > executed.txt",
            "[System.IO.File]::WriteAllText('executed.txt', 'executed')",
        ).encode("utf-8"),
        payloads=(
            BundlePayload(
                relative_path="assets/payload.bin",
                content=b"payload",
            ),
        ),
    )
    original_write = apply_mutation_module.write_bundle_payloads

    def replace_parent_before_first_stage(
        payloads: Iterable[BundlePayload],
        *,
        cwd: Path,
    ) -> None:
        parent.rmdir()
        parent.write_bytes(b"not a directory")
        original_write(payloads, cwd=cwd)

    monkeypatch.setattr(
        apply_mutation_module,
        "write_bundle_payloads",
        replace_parent_before_first_stage,
    )

    with pytest.raises(PatchHarborError) as captured:
        apply_patch_package(package, output_directory=output_directory)

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert report is not None
    assert report.primary_result.entrypoint_started is False
    assert report.result_bundle.status is ResultBundleStatus.CREATED
    assert parent.read_bytes() == b"not a directory"
    assert not (repository / "assets" / "payload.bin").exists()
    assert not (repository / "executed.txt").exists()
    assert not tuple(repository.rglob(".patchharbor-*.tmp"))

    bundle_path = report.result_bundle.path
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        blocker = archive.read("untracked/assets")

    assert blocker == b"not a directory"
    assert "untracked/assets/payload.bin" not in names
    assert "logs/execution.log" not in names


def test_payload_write_failure_keeps_partial_files_without_starting_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    output_directory = tmp_path / "results"
    entrypoint = native_script(
        "# PATCHHARBOR META invalid\nprintf executed > executed.txt",
        "# PATCHHARBOR META invalid\n"
        "[System.IO.File]::WriteAllText('executed.txt', 'executed')",
    ).encode("utf-8")
    package = _package(
        _manifest(context),
        entrypoint=entrypoint,
        payloads=(
            BundlePayload(
                relative_path="files/first.bin",
                content=b"first",
            ),
            BundlePayload(
                relative_path="files/second.bin",
                content=b"second",
            ),
        ),
    )
    original_replace = payload_files_module.atomic_replace_bytes

    def fail_second_write(target: Path, content: bytes) -> None:
        if target.name == "second.bin":
            raise FileSystemOperationError(
                "cannot replace target",
                OSError(errno.EACCES, "simulated write failure"),
            )
        original_replace(target, content)

    monkeypatch.setattr(
        payload_files_module,
        "atomic_replace_bytes",
        fail_second_write,
    )

    with pytest.raises(PatchHarborError) as captured:
        apply_patch_package(
            package,
            output_directory=output_directory,
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert report is not None
    assert report.process_exit_code == int(ExitCode.PAYLOAD_PREPARATION_ERROR)
    assert report.primary_result.kind is PrimaryResultKind.VALIDATION_ERROR
    assert report.primary_result.entrypoint_started is False
    assert report.result_bundle.status is ResultBundleStatus.CREATED
    assert report.warnings
    assert (repository / "files" / "first.bin").read_bytes() == b"first"
    assert not (repository / "files" / "second.bin").exists()
    assert not (repository / "executed.txt").exists()

    bundle_path = report.result_bundle.path
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        run = json.loads(archive.read("logs/run.json"))
        bundled_first = archive.read("untracked/files/first.bin")

    assert bundled_first == b"first"
    assert "logs/execution.log" not in names
    assert manifest["run_id"] == report.run_id_text
    assert manifest["expected_base_commit"] == str(context.base_commit)
    assert manifest["actual_base_commit"] == str(context.base_commit)
    assert manifest["expected_state_fingerprint"] == context.state_fingerprint
    assert manifest["actual_state_fingerprint"] != context.state_fingerprint
    assert run["warnings"] == list(report.warnings)
    assert run["primary_result"]["entrypoint_started"] is False
    assert probe_repository_lock(str(context.repo_id), project_environment()) == 0


def test_process_start_failure_bundles_without_claiming_entrypoint_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    output_directory = tmp_path / "results"

    private_entrypoint: Path | None = None

    def fail_process_start(
        script_path: Path,
        *args: object,
        **kwargs: object,
    ) -> ScriptExecutionResult:
        nonlocal private_entrypoint
        private_entrypoint = script_path
        return ScriptExecutionResult.failed(
            PatchHarborError(
                "cannot start script interpreter",
                ExitCode.INTERPRETER_ERROR,
            ),
            output=b"",
            entrypoint_started=False,
        )

    monkeypatch.setattr(
        application_module,
        "execute_prepared_script_with_log",
        fail_process_start,
    )

    with pytest.raises(PatchHarborError) as captured:
        apply_patch_package(
            _package(_manifest(context)),
            output_directory=output_directory,
        )

    report = captured.value.run_report
    assert captured.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert report is not None
    assert report.process_exit_code == int(ExitCode.INTERPRETER_ERROR)
    assert report.primary_result.kind is PrimaryResultKind.VALIDATION_ERROR
    assert report.primary_result.entrypoint_started is False
    assert report.result_bundle.status is ResultBundleStatus.CREATED
    bundle_path = report.result_bundle.path
    assert bundle_path is not None
    with zipfile.ZipFile(bundle_path) as archive:
        assert "logs/execution.log" not in archive.namelist()
    assert private_entrypoint is not None
    assert not private_entrypoint.exists()
    assert probe_repository_lock(str(context.repo_id), project_environment()) == 0


def test_matching_package_preflights_private_entrypoint_and_payload_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    entrypoint = (
        b"# PATCHHARBOR\r\n"
        b"# PATCHHARBOR META invalid\r\n"
        b"# PATCHHARBOR MESSAGE bad name START\r\n"
        b"# ignored\r\n"
        b"# PATCHHARBOR MESSAGE bad name END\r\n"
    )
    payload = BundlePayload(
        relative_path="files/payload.bin",
        content=b"\x00payload\xff",
    )

    entrypoint_path: Path
    environment = project_environment()
    package = _package(
        _manifest(context),
        entrypoint=entrypoint,
        payloads=(payload,),
    )
    with preflight_patch_package_repository(package) as mutation_gate:
        prepared = mutation_gate.prepared_package
        entrypoint_path = prepared.entrypoint.path

        assert mutation_gate.context == context
        assert mutation_gate.warnings
        assert entrypoint_path.read_bytes() == entrypoint
        assert entrypoint_path.suffix == (
            prepared.entrypoint.interpreter.spec.script_suffix
        )
        assert prepared.entrypoint.interpreter.executable_path
        assert prepared.payloads == (payload,)
        assert not (repository / "run.sh").exists()
        assert not (repository / "files" / "payload.bin").exists()
        assert probe_repository_lock(str(context.repo_id), environment) == int(
            ExitCode.REPOSITORY_BUSY
        )

    assert probe_repository_lock(str(context.repo_id), environment) == 0
    assert not entrypoint_path.exists()
    assert tuple(private_temp.iterdir()) == ()


def test_private_entrypoint_uses_the_resolved_interpreter_suffix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    resolved = ResolvedInterpreter(
        spec=InterpreterSpec(
            executable="powershell.exe",
            script_suffix=".ps1",
            arguments=("-File",),
        ),
        executable_path="powershell.exe",
    )
    monkeypatch.setattr(
        apply_preflight_module,
        "resolve_script_interpreter",
        lambda _script_text: resolved,
    )

    with preflight_patch_package_repository(
        _package(_manifest(context)),
    ) as mutation_gate:
        entrypoint_path = mutation_gate.prepared_package.entrypoint.path
        assert entrypoint_path.name == "script.ps1"
        assert entrypoint_path.read_text(encoding="utf-8-sig") == "# PATCHHARBOR\n"
        assert not (repository / "run.sh").exists()

    assert tuple(private_temp.iterdir()) == ()


def test_apply_preflight_presents_resolved_repository_and_entrypoint_messages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    presentation = _RecordingApplyPresentation()
    entrypoint = (
        b"# PATCHHARBOR\n"
        b"# PATCHHARBOR MESSAGE commit.last START\n"
        b"# Apply presentation connected\n"
        b"# PATCHHARBOR MESSAGE commit.last END\n"
    )

    with preflight_patch_package_repository(
        _package(_manifest(context), entrypoint=entrypoint),
        presentation=presentation,
    ):
        pass

    assert presentation.repository is not None
    assert presentation.repository["repository_name"] == str(repository.resolve())
    repository_context = presentation.repository["repository_context"]
    assert isinstance(repository_context, str)
    assert str(context.repo_id) in repository_context
    assert str(context.base_commit)[:12] in repository_context
    assert context.state_fingerprint in repository_context
    assert presentation.script == {
        "script_name": "run.sh",
        "script_index": 1,
        "script_total": 1,
        "messages": (("commit.last", "Apply presentation connected"),),
        "warnings": (),
    }


@pytest.mark.parametrize(
    ("entrypoint", "expected_exit"),
    (
        (b"printf invalid\n", ExitCode.NO_VALID_SCRIPT),
        (b"# PATCHHARBOR\n\xff", ExitCode.NO_VALID_SCRIPT),
        (
            b"#!/usr/bin/env python3\n# PATCHHARBOR\n",
            ExitCode.INTERPRETER_ERROR,
        ),
    ),
)
def test_entrypoint_preflight_rejects_invalid_scripts_without_repository_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: bytes,
    expected_exit: ExitCode,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)

    with pytest.raises(PatchHarborError) as captured:
        _complete_preflight(
            _package(
                _manifest(context),
                entrypoint=entrypoint,
                payloads=(
                    BundlePayload(
                        relative_path="files/payload.bin",
                        content=b"payload",
                    ),
                ),
            )
        )

    assert captured.value.exit_code is expected_exit
    assert tuple(private_temp.iterdir()) == ()
    assert not (repository / "run.sh").exists()
    assert not (repository / "files" / "payload.bin").exists()


def test_interpreter_availability_is_checked_before_private_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    private_writes: list[Path] = []
    original_write = apply_preflight_module.write_private_bytes

    def record_private_write(path: Path, content: bytes) -> None:
        private_writes.append(path)
        original_write(path, content)

    def missing_interpreter(_script_text: str) -> object:
        raise PatchHarborError(
            "interpreter unavailable",
            ExitCode.INTERPRETER_ERROR,
        )

    monkeypatch.setattr(
        apply_preflight_module,
        "write_private_bytes",
        record_private_write,
    )
    monkeypatch.setattr(
        apply_preflight_module,
        "resolve_script_interpreter",
        missing_interpreter,
    )

    with pytest.raises(PatchHarborError) as captured:
        _complete_preflight(
            _package(
                _manifest(context),
                payloads=(
                    BundlePayload(
                        relative_path="files/payload.bin",
                        content=b"payload",
                    ),
                ),
            )
        )

    assert captured.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert private_writes == []
    assert tuple(private_temp.iterdir()) == ()
    assert not (repository / "files" / "payload.bin").exists()
