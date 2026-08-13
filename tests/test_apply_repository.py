from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import patchharbor.result_bundle_publication as publication_module
from patchharbor.application import (
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


def _package(manifest: PatchManifest) -> ValidatedPatchPackage:
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=BundlePayload(
            relative_path="run.sh",
            content=b"# PATCHHARBOR\n",
        ),
        payloads=(),
    )


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
