from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import BinaryIO
from uuid import UUID
import zipfile

import pytest

import patchharbor.result_bundle as result_bundle_module
import patchharbor.result_bundle_capture as result_bundle_capture_module
import patchharbor.result_bundle_publication as result_bundle_publication_module
from patchharbor.cli import main as cli_main
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.platform.filesystem import MetadataSyncStatus
from patchharbor.result_bundle import create_manual_result_bundle
from patchharbor.user_paths import registration_user_paths
from tests.platform_support import project_environment, run_cli
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    probe_repository_lock,
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
    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(system_temp))
    monkeypatch.setattr(result_bundle_module.tempfile, "tempdir", str(system_temp))


def _result_bundles() -> tuple[Path, ...]:
    directory = registration_user_paths().result_directory
    if not directory.exists():
        return ()
    return tuple(sorted(directory.glob("patchharbor_result_*.zip")))


def _synchronize_after_base_capture(
    monkeypatch: pytest.MonkeyPatch,
    action: Callable[[], None],
) -> None:
    original_capture = result_bundle_capture_module.capture_base_bundle_entries

    def capture_then_act(*args: object, **kwargs: object) -> object:
        entries = original_capture(*args, **kwargs)
        action()
        return entries

    monkeypatch.setattr(
        result_bundle_capture_module,
        "capture_base_bundle_entries",
        capture_then_act,
    )


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


def test_manual_bundle_json_completion_matches_persisted_run_report(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0

    completed = run_cli(repository, "bundle", "--json")

    assert completed.returncode == 0
    assert completed.stdout.endswith("\n")
    assert "\n" not in completed.stdout[:-1]
    envelope = json.loads(completed.stdout)
    assert set(envelope) == {
        "output_version",
        "command",
        "success",
        "result",
        "error",
        "process_exit_code",
    }
    assert envelope["output_version"] == 1
    assert envelope["command"] == "bundle"
    assert envelope["success"] is True
    assert envelope["error"] is None
    assert envelope["process_exit_code"] == 0
    result = envelope["result"]
    assert isinstance(result, dict)
    assert set(result) == {
        "run_id",
        "repo_id",
        "repository_path",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "result_bundle_status",
        "result_bundle_path",
        "emergency_diagnostics_path",
    }
    assert result["repository_path"] == str(repository.resolve())
    assert result["result_bundle_status"] == "created"
    assert result["emergency_diagnostics_path"] is None
    result_path = Path(result["result_bundle_path"])
    assert result_path.is_absolute()
    assert result_path.is_file()

    with zipfile.ZipFile(result_path) as archive:
        run = json.loads(archive.read("logs/run.json"))
        assert "logs/execution.log" not in archive.namelist()

    assert run["run_id"] == result["run_id"]
    assert run["operation"] == "bundle"
    assert run["repository_path"] == result["repository_path"]
    assert run["base_commit"] == result["base_commit"]
    assert run["state_fingerprint"] == result["state_fingerprint"]
    assert run["warnings"] == []
    assert run["execution_present"] is False
    assert run["result_bundle"] == {
        "attempted": True,
        "status": "created",
        "error": None,
    }
    assert run["process_exit_code"] == 0
    assert isinstance(run["duration_seconds"], float)
    assert run["duration_seconds"] >= 0.0
    system_temp = Path(os.environ["TMPDIR"])
    assert tuple(system_temp.glob("patchharbor-*")) == ()


def test_manual_bundle_failure_returns_exit_11_and_emergency_run_report(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    forbidden_output = repository / "generated" / "results"

    completed = run_cli(
        repository,
        "bundle",
        "--json",
        "--output-dir",
        str(forbidden_output),
    )

    assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    assert completed.stdout.endswith("\n")
    assert "\n" not in completed.stdout[:-1]
    envelope = json.loads(completed.stdout)
    assert envelope["command"] == "bundle"
    assert envelope["success"] is False
    assert envelope["result"] is None
    assert envelope["process_exit_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)
    error = envelope["error"]
    assert isinstance(error, dict)
    assert set(error) == {
        "kind",
        "message",
        "patchharbor_error_code",
        "emergency_diagnostics_path",
    }
    assert error["kind"] == "result_bundle_error"
    assert error["patchharbor_error_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)
    emergency_path = Path(error["emergency_diagnostics_path"])
    assert emergency_path.is_absolute()
    assert emergency_path.is_dir()
    assert str(emergency_path) in completed.stderr
    assert not forbidden_output.exists()
    assert not tuple(repository.rglob(".patchharbor_result_*.tmp"))
    assert not tuple(repository.rglob("patchharbor_result_*.zip"))

    run = json.loads((emergency_path / "run.json").read_text(encoding="utf-8"))
    assert UUID(run["run_id"]).version == 4
    assert run["operation"] == "bundle"
    assert run["repository_resolved"] is True
    assert run["repository_path"] == str(repository.resolve())
    assert run["warnings"] == []
    assert run["execution_present"] is False
    assert run["result_bundle"]["attempted"] is True
    assert run["result_bundle"]["status"] == "failed"
    assert isinstance(run["result_bundle"]["error"], str)
    assert run["process_exit_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)


def test_manual_bundle_unresolved_repository_records_not_attempted_status(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")

    completed = run_cli(repository, "bundle", "--json")

    assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    envelope = json.loads(completed.stdout)
    emergency_path = Path(
        envelope["error"]["emergency_diagnostics_path"]
    )
    run = json.loads((emergency_path / "run.json").read_text(encoding="utf-8"))
    assert run["repository_resolved"] is False
    assert run["result_bundle"] == {
        "attempted": False,
        "status": "not_attempted",
        "error": run["result_bundle"]["error"],
    }
    assert isinstance(run["result_bundle"]["error"], str)
    assert run["process_exit_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)


def test_manual_bundle_surfaces_failed_emergency_rescue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    controlled_run_directory = tmp_path / "controlled-emergency"

    def create_controlled_run_directory(_run_id: UUID) -> Path:
        controlled_run_directory.mkdir()
        return controlled_run_directory.resolve()

    def reject_run_report(
        _run_directory: Path,
        _document: dict[str, object],
    ) -> None:
        raise OSError("simulated emergency diagnostics failure")

    monkeypatch.setattr(
        result_bundle_module,
        "_create_private_run_directory",
        create_controlled_run_directory,
    )
    monkeypatch.setattr(
        result_bundle_module,
        "_write_run_document",
        reject_run_report,
    )

    stdout = StringIO()
    stderr = StringIO()
    exit_code = cli_main(
        [
            "bundle",
            str(repository),
            "--json",
            "--output-dir",
            str(repository / "forbidden-results"),
        ],
        stdin=StringIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == int(ExitCode.RESULT_BUNDLE_ERROR)
    envelope = json.loads(stdout.getvalue())
    assert envelope["success"] is False
    assert envelope["process_exit_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)
    assert envelope["error"]["emergency_diagnostics_path"] is None
    assert stderr.getvalue().strip()
    assert not controlled_run_directory.exists()
    assert not tuple(repository.rglob("patchharbor_result_*.zip"))


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
        assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
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


def test_manual_bundle_uses_physically_resolved_explicit_output_directory(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0

    physical_output = tmp_path / "physical-results"
    physical_output.mkdir()
    requested_output = physical_output
    if os.name != "nt":
        requested_output = tmp_path / "result-link"
        requested_output.symlink_to(physical_output, target_is_directory=True)

    completed = run_cli(
        repository,
        "bundle",
        "--output-dir",
        str(requested_output),
    )

    assert completed.returncode == 0
    published = tuple(physical_output.glob("patchharbor_result_*.zip"))
    assert len(published) == 1
    assert tuple(
        path for path in physical_output.iterdir() if path != published[0]
    ) == ()
    assert _result_bundles() == ()
    with zipfile.ZipFile(published[0]) as archive:
        assert archive.testzip() is None
        assert {
            "manifest.json",
            "context.json",
            "changes/staged.patch",
            "changes/unstaged.patch",
            "logs/run.json",
        }.issubset(archive.namelist())


def test_manual_bundle_rejects_output_inside_any_registered_repository(
    tmp_path: Path,
) -> None:
    target = create_repository(tmp_path / "target")
    other = create_repository(tmp_path / "other")
    assert run_cli(target, "register").returncode == 0
    assert run_cli(other, "register").returncode == 0
    forbidden_output = other / "generated" / "results"

    completed = run_cli(
        target,
        "bundle",
        "--output-dir",
        str(forbidden_output),
    )

    assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    assert not forbidden_output.exists()
    assert _result_bundles() == ()


def test_manual_bundle_rejects_repository_change_during_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    output_directory = tmp_path / "results"

    def mutate_repository() -> None:
        (repository / "tracked.txt").write_bytes(b"changed during capture\n")

    _synchronize_after_base_capture(monkeypatch, mutate_repository)

    with pytest.raises(PatchHarborError) as captured:
        create_manual_result_bundle(
            repository,
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert output_directory.is_dir()
    assert tuple(output_directory.iterdir()) == ()


def test_manual_bundle_publishes_from_verified_temporary_zip_in_result_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    output_directory = tmp_path / "results"
    observed: dict[str, Path] = {}
    real_replace = result_bundle_publication_module.replace_path

    def observe_replace(source: object, destination: object) -> None:
        source_path = Path(source)  # type: ignore[arg-type]
        destination_path = Path(destination)  # type: ignore[arg-type]
        assert source_path.parent == output_directory.resolve()
        assert destination_path.parent == output_directory.resolve()
        assert source_path.name.startswith(".patchharbor_result_")
        assert source_path.name.endswith(".tmp")
        assert source_path.is_file()
        assert not destination_path.exists()
        with zipfile.ZipFile(source_path) as archive:
            assert archive.testzip() is None
        observed["source"] = source_path
        observed["destination"] = destination_path
        real_replace(source_path, destination_path)

    monkeypatch.setattr(
        result_bundle_publication_module,
        "replace_path",
        observe_replace,
    )

    result = create_manual_result_bundle(
        repository,
        output_directory=output_directory,
    )

    assert result.path == observed["destination"]
    assert result.path.is_file()
    assert not observed["source"].exists()
    assert tuple(output_directory.iterdir()) == (result.path,)


@pytest.mark.parametrize("verification_failure", ("missing", "crc"))
def test_manual_bundle_leaves_no_published_or_temporary_file_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verification_failure: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    output_directory = tmp_path / "results"

    if verification_failure == "missing":
        def write_incomplete(
            destination: BinaryIO,
            **_options: object,
        ) -> None:
            with zipfile.ZipFile(destination, mode="w") as archive:
                archive.writestr("manifest.json", b"{}\n")

        monkeypatch.setattr(
            result_bundle_publication_module,
            "write_result_bundle",
            write_incomplete,
        )
    else:
        monkeypatch.setattr(
            zipfile.ZipFile,
            "testzip",
            lambda self: self.namelist()[0],
        )

    with pytest.raises(PatchHarborError) as captured:
        create_manual_result_bundle(
            repository,
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert output_directory.is_dir()
    assert tuple(output_directory.iterdir()) == ()


def _create_directory_alias(alias: Path, target: Path) -> None:
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip("Windows directory junctions are unavailable")
        return
    alias.symlink_to(target, target_is_directory=True)


def test_manual_bundle_rejects_physical_output_alias_inside_repository(
    tmp_path: Path,
) -> None:
    target = create_repository(tmp_path / "target")
    other = create_repository(tmp_path / "other")
    assert run_cli(target, "register").returncode == 0
    assert run_cli(other, "register").returncode == 0
    alias = tmp_path / "other-alias"
    _create_directory_alias(alias, other)
    forbidden_output = alias / "generated" / "results"

    completed = run_cli(
        target,
        "bundle",
        "--output-dir",
        str(forbidden_output),
    )

    assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    assert not (other / "generated").exists()
    assert _result_bundles() == ()


def test_manual_bundle_holds_repository_lock_through_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    environment = project_environment()
    real_replace = result_bundle_publication_module.replace_path
    observed: list[int] = []

    def replace_while_probing(source: Path, destination: Path) -> None:
        observed.append(probe_repository_lock(repo_id, environment))
        real_replace(source, destination)

    monkeypatch.setattr(
        result_bundle_publication_module,
        "replace_path",
        replace_while_probing,
    )

    result = create_manual_result_bundle(
        repository,
        output_directory=tmp_path / "results",
    )

    assert result.path.is_file()
    assert observed == [int(ExitCode.REPOSITORY_BUSY)]
    assert probe_repository_lock(repo_id, environment) == 0


def test_manual_bundle_reports_best_effort_sync_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    directory_statuses = iter(
        (MetadataSyncStatus.UNSUPPORTED, MetadataSyncStatus.FAILED)
    )
    monkeypatch.setattr(
        result_bundle_publication_module,
        "sync_regular_file_best_effort",
        lambda _path: MetadataSyncStatus.FAILED,
    )
    monkeypatch.setattr(
        result_bundle_publication_module,
        "sync_directory_best_effort",
        lambda _path: next(directory_statuses),
    )

    result = create_manual_result_bundle(
        repository,
        output_directory=tmp_path / "results",
    )

    assert result.path.is_file()
    assert result.publication_durability.temporary_file is MetadataSyncStatus.FAILED
    assert (
        result.publication_durability.directory_before_replace
        is MetadataSyncStatus.UNSUPPORTED
    )
    assert (
        result.publication_durability.directory_after_replace
        is MetadataSyncStatus.FAILED
    )


def test_manual_bundle_rejects_output_directory_retargeted_during_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    other = create_repository(tmp_path / "other")
    assert run_cli(repository, "register").returncode == 0
    assert run_cli(other, "register").returncode == 0
    output_directory = tmp_path / "results"
    moved_directory = tmp_path / "original-results"

    def retarget_output_directory() -> None:
        output_directory.rename(moved_directory)
        _create_directory_alias(output_directory, other)

    _synchronize_after_base_capture(monkeypatch, retarget_output_directory)

    with pytest.raises(PatchHarborError) as captured:
        create_manual_result_bundle(
            repository,
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert not tuple(other.glob("patchharbor_result_*.zip"))
    assert tuple(moved_directory.iterdir()) == ()


def test_manual_bundle_holds_and_releases_lock_when_publication_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    environment = project_environment()
    observed: list[int] = []
    output_directory = tmp_path / "results"

    def fail_while_probing(
        destination: BinaryIO,
        **_options: object,
    ) -> None:
        observed.append(probe_repository_lock(repo_id, environment))
        destination.write(b"partial bundle")
        destination.flush()
        raise OSError("simulated publication failure")

    monkeypatch.setattr(
        result_bundle_publication_module,
        "write_result_bundle",
        fail_while_probing,
    )

    with pytest.raises(PatchHarborError) as captured:
        create_manual_result_bundle(
            repository,
            output_directory=output_directory,
        )

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert observed == [int(ExitCode.REPOSITORY_BUSY)]
    assert tuple(output_directory.iterdir()) == ()
    assert probe_repository_lock(repo_id, environment) == 0
