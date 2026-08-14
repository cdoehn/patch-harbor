from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

import pytest

import patchharbor.apply_preflight as apply_preflight_module
import patchharbor.result_bundle_publication as publication_module
from patchharbor.application import (
    preflight_patch_package_repository,
    register_repository,
    validate_patch_package_repository,
)
from patchharbor.apply_repository import safely_resolved_repository
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundlePayload, RepositoryContext
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MARKER,
    PatchManifest,
)
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.run_report import RunSession
from tests.platform_support import project_environment
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
        validate_patch_package_repository(
            _package(manifest),
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.STATE_MISMATCH
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(str(context.repo_id), environment) == 0
    bundles = tuple(output_directory.glob("patchharbor_result_*.zip"))
    assert len(bundles) == 1
    assert not tuple(output_directory.glob(".*.tmp"))



def test_matching_package_preflights_private_resources_and_cleans_them(
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
    payload_path: Path
    environment = project_environment()
    with preflight_patch_package_repository(
        _package(
            _manifest(context),
            entrypoint=entrypoint,
            payloads=(payload,),
        )
    ) as preflight:
        prepared = preflight.prepared_package
        entrypoint_path = prepared.entrypoint.path
        payload_path = prepared.payloads[0].path

        assert preflight.context == context
        assert preflight.warnings
        assert entrypoint_path.read_bytes() == entrypoint
        assert prepared.entrypoint.size_bytes == len(entrypoint)
        assert len(prepared.entrypoint.sha256_hex) == 64
        assert prepared.entrypoint.interpreter.executable_path
        assert prepared.payloads[0].relative_path == "files/payload.bin"
        assert payload_path.read_bytes() == payload.content
        assert prepared.payloads[0].size_bytes == len(payload.content)
        assert len(prepared.payloads[0].sha256_hex) == 64
        assert not (repository / "run.sh").exists()
        assert not (repository / "files" / "payload.bin").exists()
        assert probe_repository_lock(str(context.repo_id), environment) == int(
            ExitCode.REPOSITORY_BUSY
        )

    assert probe_repository_lock(str(context.repo_id), environment) == 0
    assert not entrypoint_path.exists()
    assert not payload_path.exists()
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
        validate_patch_package_repository(
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


def test_payload_preflight_detects_staged_content_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    original_write = apply_preflight_module.write_private_bytes

    def write_corrupted_payload(path: Path, content: bytes) -> None:
        if "payloads" in path.parts:
            original_write(path, content + b"corruption")
        else:
            original_write(path, content)

    monkeypatch.setattr(
        apply_preflight_module,
        "write_private_bytes",
        write_corrupted_payload,
    )

    with pytest.raises(PatchHarborError) as captured:
        validate_patch_package_repository(
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

    assert captured.value.exit_code is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert tuple(private_temp.iterdir()) == ()
    assert not (repository / "files" / "payload.bin").exists()


def test_interpreter_availability_is_checked_before_payload_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    private_temp = tmp_path / "private-temp"
    _set_private_temp(monkeypatch, private_temp)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    staged_roles: list[str] = []
    original_write = apply_preflight_module.write_private_bytes

    def record_private_write(path: Path, content: bytes) -> None:
        staged_roles.append(
            "payload" if "payloads" in path.parts else "entrypoint"
        )
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
        validate_patch_package_repository(
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
    assert staged_roles == ["entrypoint"]
    assert tuple(private_temp.iterdir()) == ()
    assert not (repository / "files" / "payload.bin").exists()
