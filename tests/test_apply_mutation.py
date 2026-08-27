from __future__ import annotations

from pathlib import Path

import pytest

import patchharbor.apply_mutation as mutation_module
from patchharbor.application import (
    preflight_patch_package_repository,
    register_repository,
)
from patchharbor.apply_mutation import (
    MutationFailureKind,
    apply_payload_mutation,
)
from patchharbor.configuration import write_exchange_directory
from patchharbor.errors import ExitCode, PatchHarborError, patch_package_error
from patchharbor.models import BundlePayload, RepositoryContext
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MARKER,
    PatchManifest,
)
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.payload_files import PayloadTargetError, PayloadWriteError
from patchharbor.user_paths import registration_user_paths
from tests.platform_support import project_environment
from tests.registration_support import (
    create_repository,
    probe_repository_lock,
    set_isolated_user_environment,
)


pytestmark = pytest.mark.e2e


def _package(
    context: RepositoryContext,
    *,
    payloads: tuple[BundlePayload, ...],
) -> ValidatedPatchPackage:
    manifest = PatchManifest(
        marker=PATCH_MARKER,
        format_version=PATCH_FORMAT_VERSION,
        repo_id=context.repo_id,
        base_commit=context.base_commit,
        state_fingerprint=context.state_fingerprint,
        fingerprint_algorithm=context.fingerprint_algorithm,
        entrypoint="run.sh",
    )
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=BundlePayload("run.sh", b"# PATCHHARBOR\n"),
        payloads=payloads,
    )


def _configure_exchange(tmp_path: Path) -> None:
    write_exchange_directory(
        registration_user_paths(),
        tmp_path / "exchange",
    )


def test_mutation_boundary_rechecks_and_writes_while_repository_is_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    payload = BundlePayload("files/payload.bin", b"payload")
    package = _package(context, payloads=(payload,))
    observed_lock_codes: list[int] = []
    original_write = mutation_module.write_bundle_payloads

    def write_while_observing_lock(
        payloads: tuple[BundlePayload, ...],
        *,
        cwd: Path,
    ) -> None:
        observed_lock_codes.append(
            probe_repository_lock(str(context.repo_id), project_environment())
        )
        original_write(payloads, cwd=cwd)

    monkeypatch.setattr(
        mutation_module,
        "write_bundle_payloads",
        write_while_observing_lock,
    )

    with preflight_patch_package_repository(package, dry_run=False) as gate:
        result = apply_payload_mutation(gate)

    assert result.success is True
    assert result.failure_kind is None
    assert result.error is None
    assert result.context == context
    assert observed_lock_codes == [int(ExitCode.REPOSITORY_BUSY)]
    assert (repository / "files" / "payload.bin").read_bytes() == b"payload"
    assert not tuple(repository.rglob(".patchharbor-*.tmp"))


def test_mutation_boundary_reports_changed_state_without_payload_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    package = _package(
        context,
        payloads=(BundlePayload("payload.bin", b"payload"),),
    )

    with preflight_patch_package_repository(package, dry_run=False) as gate:
        (repository / "external.txt").write_bytes(b"external")
        result = apply_payload_mutation(gate)

    assert result.success is False
    assert result.failure_kind is MutationFailureKind.STATE_MISMATCH
    assert result.error is not None
    assert result.error.exit_code is ExitCode.STATE_MISMATCH
    assert result.context.state_fingerprint != context.state_fingerprint
    assert not (repository / "payload.bin").exists()
    assert not tuple(repository.rglob(".patchharbor-*.tmp"))


@pytest.mark.parametrize(
    ("error_type", "expected_kind"),
    (
        (PayloadTargetError, MutationFailureKind.UNSAFE_TARGET),
        (PayloadWriteError, MutationFailureKind.WRITE_FAILURE),
    ),
)
def test_mutation_boundary_keeps_target_and_write_failures_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[PayloadTargetError] | type[PayloadWriteError],
    expected_kind: MutationFailureKind,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    package = _package(
        context,
        payloads=(BundlePayload("payload.bin", b"payload"),),
    )

    def fail_write(
        _payloads: tuple[BundlePayload, ...],
        *,
        cwd: Path,
    ) -> None:
        assert cwd == repository
        raise error_type(
            "simulated mutation failure",
            ExitCode.PAYLOAD_PREPARATION_ERROR,
        )

    monkeypatch.setattr(mutation_module, "write_bundle_payloads", fail_write)

    with preflight_patch_package_repository(package, dry_run=False) as gate:
        result = apply_payload_mutation(gate)

    assert result.success is False
    assert result.failure_kind is expected_kind
    assert result.error is not None
    assert result.error.exit_code is ExitCode.PAYLOAD_PREPARATION_ERROR
    assert result.context == context
    assert not (repository / "payload.bin").exists()


def test_attempt_publication_runs_after_state_check_and_before_payload_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    target = repository / "payload.bin"
    observations: list[tuple[bool, int]] = []

    def publish_attempt() -> None:
        observations.append(
            (
                target.exists(),
                probe_repository_lock(
                    str(context.repo_id),
                    project_environment(),
                ),
            )
        )

    package = _package(
        context,
        payloads=(BundlePayload("payload.bin", b"payload"),),
    )
    with preflight_patch_package_repository(
        package,
        dry_run=False,
        before_mutation=publish_attempt,
    ) as gate:
        result = apply_payload_mutation(gate)

    assert result.success is True
    assert observations == [(False, int(ExitCode.REPOSITORY_BUSY))]
    assert target.read_bytes() == b"payload"


def test_failed_attempt_publication_prevents_every_repository_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    target = repository / "payload.bin"

    def fail_attempt_publication() -> None:
        assert not target.exists()
        raise patch_package_error("cannot publish automatic attempt")

    package = _package(
        context,
        payloads=(BundlePayload("payload.bin", b"payload"),),
    )
    with preflight_patch_package_repository(
        package,
        dry_run=False,
        before_mutation=fail_attempt_publication,
    ) as gate:
        with pytest.raises(
            PatchHarborError,
            match="cannot publish automatic attempt",
        ):
            apply_payload_mutation(gate)

    assert not target.exists()


def test_state_mismatch_prevents_attempt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    _configure_exchange(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = register_repository(repository)
    publications: list[bool] = []
    package = _package(
        context,
        payloads=(BundlePayload("payload.bin", b"payload"),),
    )

    with preflight_patch_package_repository(
        package,
        dry_run=False,
        before_mutation=lambda: publications.append(True),
    ) as gate:
        (repository / "external.txt").write_bytes(b"changed")
        result = apply_payload_mutation(gate)

    assert result.failure_kind is MutationFailureKind.STATE_MISMATCH
    assert publications == []
    assert not (repository / "payload.bin").exists()
