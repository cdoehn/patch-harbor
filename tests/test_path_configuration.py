from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.locks import registry_lock
from patchharbor.models import RegistrySnapshot
from patchharbor.path_configuration import (
    PathConfigurationError,
    load_configured_paths,
    prepare_watcher_input_directory,
)
from patchharbor.platform.paths import (
    is_physically_within,
    physical_paths_overlap,
)
from patchharbor.registration import register_local_repository
from patchharbor.result_bundle_target import prepare_result_bundle_target
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import (
    create_repository,
    set_isolated_user_environment,
)


def _empty_registry() -> RegistrySnapshot:
    return RegistrySnapshot(repositories=())


def _prepare_result_directory(directory: Path) -> None:
    paths = registration_user_paths()
    with registry_lock(paths):
        prepare_result_bundle_target(
            directory,
            _empty_registry(),
            paths,
            filename="result.zip",
        )


@pytest.mark.parametrize("relationship", ["equal", "inside"])
def test_watcher_input_rejects_repository_root_and_descendants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relationship: str,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    register_local_repository(repository)
    if relationship == "equal":
        requested = repository
    else:
        requested = repository / "incoming"
        requested.mkdir()

    with pytest.raises(PathConfigurationError):
        prepare_watcher_input_directory(requested)


def test_watcher_input_may_contain_a_registered_repository_because_scan_is_flat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    repository = create_repository(incoming / "repository")
    register_local_repository(repository)

    prepared = prepare_watcher_input_directory(incoming)

    assert prepared.directory == incoming.resolve()


@pytest.mark.parametrize("relationship", ["inside", "contains"])
def test_result_directory_rejects_overlap_with_configured_watcher_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relationship: str,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    watcher = tmp_path / "incoming"
    watcher.mkdir()
    prepare_watcher_input_directory(watcher)
    result = watcher / "results" if relationship == "inside" else tmp_path

    with pytest.raises(PatchHarborError) as captured:
        _prepare_result_directory(result)

    assert captured.value.exit_code is ExitCode.RESULT_BUNDLE_ERROR


def test_watcher_input_rejects_default_result_directory_before_first_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    default_result = registration_user_paths().result_directory
    default_result.mkdir(parents=True)

    with pytest.raises(PathConfigurationError):
        prepare_watcher_input_directory(default_result)


@pytest.mark.parametrize("relationship", ["inside", "contains"])
def test_watcher_input_rejects_overlap_with_recorded_result_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relationship: str,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    result = tmp_path / "results"
    _prepare_result_directory(result)
    if relationship == "inside":
        watcher = result / "incoming"
        watcher.mkdir()
    else:
        watcher = tmp_path

    with pytest.raises(PathConfigurationError):
        prepare_watcher_input_directory(watcher)


def test_registration_rejects_repository_overlapping_configured_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    incoming = repository / "incoming"
    incoming.mkdir()
    prepare_watcher_input_directory(incoming)

    with pytest.raises(PatchHarborError) as captured:
        register_local_repository(repository)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert not (repository / ".patchharbor").exists()


def test_registration_allows_repository_below_flat_watcher_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    prepare_watcher_input_directory(incoming)
    repository = create_repository(incoming / "repository")

    repo_id, registered = register_local_repository(repository)

    assert registered.value == repository.resolve()
    assert (
        repository / ".patchharbor" / "id"
    ).read_text(encoding="ascii").strip() == str(repo_id)


def test_registration_rejects_repository_containing_recorded_result_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    result = repository / "results"
    _prepare_result_directory(result)

    with pytest.raises(PatchHarborError) as captured:
        register_local_repository(repository)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert not (repository / ".patchharbor").exists()


def test_watcher_and_result_directories_are_persisted_canonically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    prepared = prepare_watcher_input_directory(incoming)
    result = tmp_path / "results"
    _prepare_result_directory(result)

    configured = load_configured_paths(registration_user_paths())

    assert configured.watcher_input_directories == (incoming.resolve(),)
    assert set(configured.result_directories) == {
        registration_user_paths().result_directory.resolve(),
        result.resolve(),
    }
    assert prepared.directory == incoming.resolve()
    assert prepared.state_path.parent == registration_user_paths().watcher_state_directory


def _directory_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")


def test_watcher_boundary_uses_physical_target_of_directory_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    register_local_repository(repository)
    incoming = repository / "incoming"
    incoming.mkdir()
    alias = tmp_path / "incoming-alias"
    _directory_symlink_or_skip(alias, incoming)

    with pytest.raises(PathConfigurationError):
        prepare_watcher_input_directory(alias)


@pytest.mark.parametrize(
    ("candidate_parts", "expected"),
    [
        (("project", "incoming"), True),
        (("project-downloads",), False),
    ],
)
def test_physical_path_relations_use_path_components(
    tmp_path: Path,
    candidate_parts: tuple[str, ...],
    expected: bool,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    candidate = tmp_path.joinpath(*candidate_parts)
    candidate.mkdir(parents=True, exist_ok=True)

    assert is_physically_within(
        candidate,
        root,
        candidate_must_exist=True,
        root_must_exist=True,
    ) is expected
    assert physical_paths_overlap(
        candidate,
        root,
        first_must_exist=True,
        second_must_exist=True,
    ) is expected
