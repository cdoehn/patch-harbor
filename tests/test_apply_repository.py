from __future__ import annotations

from dataclasses import replace
import errno
import json
from pathlib import Path
import tempfile
import zipfile

import pytest

import patchharbor.apply_preflight as apply_preflight_module
import patchharbor.payload_files as payload_files_module
import patchharbor.result_bundle_publication as publication_module
from patchharbor.application import (
    apply_patch_package,
    dry_run_patch_package,
    preflight_patch_package_repository,
    register_repository,
)
from patchharbor.apply_repository import safely_resolved_repository
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload, RepositoryContext
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
