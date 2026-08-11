from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
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


def _result_bundles() -> tuple[Path, ...]:
    directory = registration_user_paths().result_directory
    if not directory.exists():
        return ()
    return tuple(sorted(directory.glob("patchharbor_result_*.zip")))


def _assert_rfc3339_utc(value: object) -> None:
    assert isinstance(value, str)
    assert value.endswith("Z")
    datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


def _materialize_base_repository(
    archive: zipfile.ZipFile,
    destination: Path,
) -> Path:
    destination.mkdir()
    git(destination, "init", "--quiet")
    git(destination, "config", "user.name", "PatchHarbor Test")
    git(destination, "config", "user.email", "patchharbor@example.invalid")

    base_entries = tuple(
        info for info in archive.infolist() if info.filename.startswith("base/")
    )
    for info in base_entries:
        relative_path = info.filename.removeprefix("base/")
        target = destination.joinpath(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))

    git(destination, "add", "--all")
    for info in base_entries:
        relative_path = info.filename.removeprefix("base/")
        executable = bool((info.external_attr >> 16) & stat.S_IXUSR)
        git(
            destination,
            "update-index",
            "--chmod=+x" if executable else "--chmod=-x",
            "--",
            relative_path,
        )
    git(destination, "commit", "--quiet", "-m", "materialized base")
    return destination


def _apply_patch(
    repository: Path,
    patch: bytes,
    *arguments: str,
) -> None:
    """Apply raw bundle patch bytes without a filesystem intermediary."""
    subprocess.run(
        ["git", "apply", *arguments, "--binary"],
        cwd=repository,
        input=patch,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _tracked_worktree(repository: Path) -> dict[str, bytes | None]:
    raw_paths = git(repository, "ls-files", "-z").stdout
    return {
        relative_path: (
            repository.joinpath(*relative_path.split("/")).read_bytes()
            if repository.joinpath(*relative_path.split("/")).is_file()
            else None
        )
        for relative_path in raw_paths.rstrip("\0").split("\0")
        if relative_path
    }


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
        "executable.sh": b"#!/bin/sh\nexit 0\n",
        "nested/data.bin": b"binary\x00payload\xff\r\n",
        "substituted.txt": b"commit=$Format:%H$\n",
    }
    for relative_path, content in committed.items():
        target = repository.joinpath(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if relative_path == "executable.sh":
            os.chmod(target, 0o755)
    git(repository, "add", "--all")
    git(repository, "update-index", "--chmod=+x", "executable.sh")
    git(repository, "commit", "--quiet", "-m", "base with export attributes")
    assert run_cli(repository, "register").returncode == 0

    invocation_directory = tmp_path if explicit_path else repository
    arguments = (str(repository),) if explicit_path else ()
    completed = run_cli(invocation_directory, "bundle", *arguments)

    assert completed.returncode == 0
    bundles = _result_bundles()
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        archive_names = archive.namelist()
        names = set(archive_names)
        expected_base_names = {f"base/{path}" for path in committed}
        base_names_in_archive_order = [
            name.removeprefix("base/")
            for name in archive_names
            if name.startswith("base/")
        ]
        assert [name.encode("utf-8") for name in base_names_in_archive_order] == sorted(
            name.encode("utf-8") for name in base_names_in_archive_order
        )
        assert names == expected_base_names | {
            "manifest.json",
            "context.json",
            "changes/staged.patch",
            "changes/unstaged.patch",
            "logs/run.json",
        }
        for relative_path, expected_content in committed.items():
            assert archive.read(f"base/{relative_path}") == expected_content
        executable_mode = archive.getinfo("base/executable.sh").external_attr >> 16
        assert executable_mode & 0o777 == 0o755

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
    expected_base_entries = [
        {
            "path": relative_path,
            "git_mode": (
                "100755" if relative_path == "executable.sh" else "100644"
            ),
            "object_id": git(
                repository,
                "rev-parse",
                f"HEAD:{relative_path}",
            ).stdout.strip(),
            "size": len(committed[relative_path]),
        }
        for relative_path in sorted(
            committed,
            key=lambda path: path.encode("utf-8"),
        )
    ]
    assert manifest["base_entries"] == expected_base_entries
    assert manifest["untracked_entries"] == []
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


def test_manual_bundle_captures_untracked_bytes_modes_and_hashes(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository", with_commit=False)
    (repository / ".gitignore").write_bytes(
        b"ignored.bin\nignored-directory/\n.env\n"
    )
    (repository / "base.txt").write_bytes(b"committed base\n")
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "base with ignore rules")
    assert run_cli(repository, "register").returncode == 0

    untracked = {
        "tools/local.sh": b"#!/bin/sh\nprintf local\n",
        "notes/token.txt": b"API_KEY=not-filtered\n",
        "artifacts/binary.dat": b"binary\x00payload\xff\r\n",
    }
    for relative_path, content in untracked.items():
        target = repository.joinpath(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    expected_executable_mode = "100644"
    if os.name != "nt":
        git(repository, "config", "core.filemode", "true")
        os.chmod(repository / "tools/local.sh", 0o755)
        expected_executable_mode = "100755"

    (repository / "ignored.bin").write_bytes(b"ignored\x00secret")
    (repository / ".env").write_bytes(b"TOKEN=ignored-secret\n")
    (repository / "ignored-directory").mkdir()
    (repository / "ignored-directory" / "secret.txt").write_bytes(b"ignored")

    completed = run_cli(repository, "bundle")

    assert completed.returncode == 0
    bundles = _result_bundles()
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        entries = manifest["untracked_entries"]
        entry_paths = [entry["path"] for entry in entries]

        assert [path.encode("utf-8") for path in entry_paths] == sorted(
            path.encode("utf-8") for path in untracked
        )
        for entry in entries:
            relative_path = entry["path"]
            content = archive.read(f"untracked/{relative_path}")
            expected_mode = (
                expected_executable_mode
                if relative_path == "tools/local.sh"
                else "100644"
            )
            archived_mode = (
                archive.getinfo(f"untracked/{relative_path}").external_attr
                >> 16
            )

            assert content == untracked[relative_path]
            assert entry == {
                "path": relative_path,
                "mode": expected_mode,
                "size": len(content),
                "sha256": sha256(content).hexdigest(),
            }
            assert archived_mode & 0o777 == int(expected_mode[-3:], 8)

        assert "untracked/ignored.bin" not in names
        assert "untracked/.env" not in names
        assert "untracked/ignored-directory/secret.txt" not in names
        assert not any(".patchharbor" in name.casefold() for name in names)

    assert manifest["dirty"] is True
    assert [entry["path"] for entry in manifest["base_entries"]] == [
        ".gitignore",
        "base.txt",
    ]


def test_manual_bundle_patches_reconstruct_staged_and_unstaged_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository", with_commit=False)
    base_files = {
        ".gitattributes": b"*.bin diff=patchharbor-unsafe\n",
        "layered.bin": b"base-layer\x00\xff\n",
        "staged-only.bin": b"base-staged\x00\n",
        "unstaged-only.bin": b"base-unstaged\x00\n",
        "staged-mode.sh": b"#!/bin/sh\nexit 0\n",
        "unstaged-mode.sh": b"#!/bin/sh\nexit 0\n",
    }
    for relative_path, content in base_files.items():
        (repository / relative_path).write_bytes(content)
    if os.name != "nt":
        os.chmod(repository / "unstaged-mode.sh", 0o755)
        git(repository, "config", "core.filemode", "true")
    git(repository, "add", "--all")
    git(repository, "update-index", "--chmod=+x", "unstaged-mode.sh")
    git(repository, "commit", "--quiet", "-m", "binary and mode base")
    git(
        repository,
        "config",
        "diff.external",
        "patchharbor-external-diff-must-not-run",
    )
    git(
        repository,
        "config",
        "diff.patchharbor-unsafe.textconv",
        "patchharbor-textconv-must-not-run",
    )
    git(repository, "config", "color.ui", "always")
    git(repository, "config", "diff.renames", "true")
    monkeypatch.setenv(
        "GIT_EXTERNAL_DIFF",
        "patchharbor-environment-diff-must-not-run",
    )
    monkeypatch.setenv("GIT_DIFF_OPTS", "--stat")
    assert run_cli(repository, "register").returncode == 0

    (repository / "layered.bin").write_bytes(b"staged-layer\x00\xfe\n")
    (repository / "staged-only.bin").write_bytes(b"staged-only\x00\xfd\n")
    git(repository, "add", "layered.bin", "staged-only.bin")
    git(repository, "update-index", "--chmod=+x", "staged-mode.sh")
    if os.name != "nt":
        os.chmod(repository / "staged-mode.sh", 0o755)

    (repository / "layered.bin").write_bytes(b"working-layer\x00\xfc\n")
    (repository / "unstaged-only.bin").write_bytes(
        b"unstaged-only\x00\xfb\n"
    )
    if os.name != "nt":
        os.chmod(repository / "unstaged-mode.sh", 0o644)

    base_commit = git(repository, "rev-parse", "HEAD").stdout.strip()
    source_index_tree = git(repository, "write-tree").stdout.strip()

    completed = run_cli(repository, "bundle")

    assert completed.returncode == 0
    bundles = _result_bundles()
    assert len(bundles) == 1
    reconstructed = tmp_path / "reconstructed"
    with zipfile.ZipFile(bundles[0]) as archive:
        staged_patch = archive.read("changes/staged.patch")
        unstaged_patch = archive.read("changes/unstaged.patch")
        context = json.loads(archive.read("context.json"))
        _materialize_base_repository(archive, reconstructed)

    assert context["dirty"] is True
    assert context["base_commit"] == base_commit

    _apply_patch(reconstructed, staged_patch, "--index")
    assert git(reconstructed, "write-tree").stdout.strip() == source_index_tree

    _apply_patch(reconstructed, unstaged_patch)
    assert git(reconstructed, "write-tree").stdout.strip() == source_index_tree
    assert _tracked_worktree(reconstructed) == _tracked_worktree(repository)

    if os.name != "nt":
        for relative_path in ("staged-mode.sh", "unstaged-mode.sh"):
            expected_mode = (repository / relative_path).stat().st_mode
            reconstructed_mode = (reconstructed / relative_path).stat().st_mode
            assert bool(expected_mode & stat.S_IXUSR) == bool(
                reconstructed_mode & stat.S_IXUSR
            )


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


def test_manual_bundle_keeps_the_committed_lfs_pointer_without_smudging(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository", with_commit=False)
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:" + (b"a" * 64) + b"\n"
        b"size 123456\n"
    )
    (repository / ".gitattributes").write_bytes(b"large.bin filter=lfs\n")
    (repository / "large.bin").write_bytes(pointer)
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "base with LFS pointer")

    git(repository, "config", "filter.lfs.clean", "cat")
    git(
        repository,
        "config",
        "filter.lfs.smudge",
        "patchharbor-smudge-must-not-run",
    )
    git(repository, "config", "filter.lfs.required", "true")
    assert run_cli(repository, "register").returncode == 0

    completed = run_cli(repository, "bundle")

    assert completed.returncode == 0
    bundles = _result_bundles()
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        assert archive.read("base/large.bin") == pointer
