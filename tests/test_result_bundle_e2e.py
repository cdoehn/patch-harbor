from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID
import zipfile

import pytest

from patchharbor.user_paths import registration_user_paths
from tests.platform_support import project_environment, run_cli
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def isolate_bundle_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in isolated_user_environment(tmp_path / "user").items():
        monkeypatch.setenv(name, value)


def _git_bytes(repository: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout


def _result_bundles() -> tuple[Path, ...]:
    directory = registration_user_paths().result_directory
    if not directory.exists():
        return ()
    return tuple(sorted(directory.glob("patchharbor_result_*.zip")))


def _assert_rfc3339_utc(value: object) -> None:
    assert isinstance(value, str)
    assert value.endswith("Z")
    datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


@pytest.mark.parametrize("explicit_path", [False, True])
def test_manual_bundle_materializes_committed_blobs_without_export_rules(
    tmp_path: Path,
    explicit_path: bool,
) -> None:
    repository = create_repository(tmp_path / "repository", with_commit=False)
    (repository / "nested").mkdir()
    committed = {
        ".gitattributes": (
            b"exported-away.txt export-ignore\n"
            b"substituted.txt export-subst\n"
        ),
        "exported-away.txt": b"still committed\x00bytes\n",
        "nested/data.bin": b"binary\x00payload\xff\r\n",
        "substituted.txt": b"commit=$Format:%H$\n",
    }
    for relative_path, content in committed.items():
        target = repository.joinpath(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "base with export attributes")
    assert run_cli(repository, "register").returncode == 0

    invocation_directory = tmp_path if explicit_path else repository
    arguments = (str(repository),) if explicit_path else ()
    completed = run_cli(invocation_directory, "bundle", *arguments)

    assert completed.returncode == 0
    bundles = _result_bundles()
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        names = set(archive.namelist())
        expected_base_names = {f"base/{path}" for path in committed}
        assert expected_base_names.issubset(names)
        assert {name for name in names if name.startswith("base/")} == (
            expected_base_names
        )
        assert {"manifest.json", "context.json", "logs/run.json"}.issubset(
            names
        )
        assert "logs/execution.log" not in names
        assert not any(
            segment.casefold() in {".git", ".patchharbor"}
            for name in names
            for segment in name.split("/")
        )

        for relative_path in committed:
            assert archive.read(f"base/{relative_path}") == _git_bytes(
                repository,
                "show",
                f"HEAD:{relative_path}",
            )

        manifest = json.loads(archive.read("manifest.json"))
        context = json.loads(archive.read("context.json"))
        run = json.loads(archive.read("logs/run.json"))

    run_id = UUID(manifest["run_id"])
    assert run_id.version == 4
    assert str(run_id) == manifest["run_id"]
    assert manifest["marker"] == "patch-harbor-result-bundle"
    assert manifest["format_version"] == 1
    assert manifest["dirty"] is False
    assert manifest["execution_present"] is False
    assert manifest["primary_result"] == "success"
    assert manifest["result_bundle_status"] == "created"
    _assert_rfc3339_utc(manifest["created_at"])

    expected_commit = git(repository, "rev-parse", "HEAD").stdout.strip()
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    assert context == {
        "repo_id": repo_id,
        "base_commit": expected_commit,
        "dirty": False,
        "state_fingerprint": "7c9d2a24e397e0e5",
        "fingerprint_algorithm": "patchharbor-state-v1",
        "created_at": manifest["created_at"],
    }
    assert manifest["repo_id"] == context["repo_id"]
    assert manifest["base_commit"] == context["base_commit"]
    assert manifest["state_fingerprint"] == context["state_fingerprint"]
    assert run["run_id"] == manifest["run_id"]
    assert run["operation"] == "bundle"
    assert run["repository_resolved"] is True
    assert run["repository_path"] == str(repository.resolve())
    assert run["execution_present"] is False
    assert run["primary_result"]["entrypoint_started"] is False
    assert run["result_bundle"]["status"] == "created"
    assert run["process_exit_code"] == 0
    _assert_rfc3339_utc(run["started_at"])
    _assert_rfc3339_utc(run["ended_at"])


def test_manual_bundle_respects_the_repository_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    holder = start_repository_lock_holder(
        repo_id,
        environment=project_environment(),
    )
    try:
        completed = run_cli(repository, "bundle")
        assert completed.returncode == 12
        assert _result_bundles() == ()
        assert release_repository_lock_holder(holder) == 0
    finally:
        stop_repository_lock_holder(holder)
