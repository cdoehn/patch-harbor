from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from tests.platform_support import run_cli
from tests.registration_support import create_repository, git, exchange_state_path, user_configuration_path
from tests.test_exchange_e2e import (
    _configure_user, _register_context, _write_custom_package, _identity_record,
)


pytestmark = pytest.mark.e2e
ARCHIVE = "PatchHarbor-Archive"


def _world(tmp_path):
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repo-a")
    context = _register_context(repository, environment)
    return environment, exchange, repository, context


def _bundle(repository, environment):
    completed = run_cli(repository, "bundle", "--json", environment_overrides=environment)
    assert completed.returncode == 0, completed.stderr
    return Path(json.loads(completed.stdout)["result"]["result_bundle_path"])


def _advance(repository, message="next state"):
    git(repository, "commit", "--allow-empty", "-m", message)


def _scan(repository, environment, *, automatic=False):
    arguments = ("--automatic",) if automatic else ()
    return run_cli(repository, "apply", "--json", *arguments, environment_overrides=environment)


def _committing_patch(path, context):
    _write_custom_package(
        path, context,
        posix_entrypoint="git commit --allow-empty -m archive-test >/dev/null",
        powershell_entrypoint="git commit --allow-empty -m archive-test; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
    )


def _rewrite(path, mutate):
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    mutate(files)
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)


@pytest.mark.parametrize("name", [ARCHIVE, ".PatchHarbor-Archive", "My-Archive"])
def test_archive_configuration_and_automatic_child_creation(tmp_path, name):
    env, exchange, repo, _ = _world(tmp_path)
    if name != ARCHIVE:
        changed = run_cli(repo, "configure", "archive-dir", name, environment_overrides=env)
        assert changed.returncode == 0, changed.stderr
    assert not (exchange / name).exists()
    assert _scan(repo, env).returncode == 10
    assert (exchange / name).is_dir()
    shown = run_cli(repo, "configure", "show", environment_overrides=env)
    assert f"archive_directory: {name}" in shown.stdout


@pytest.mark.parametrize("disable", [("--clear",), ("",)])
def test_empty_setting_completely_disables_archival(tmp_path, disable):
    env, exchange, repo, _ = _world(tmp_path)
    assert run_cli(repo, "configure", "archive-dir", *disable, environment_overrides=env).returncode == 0
    old = _bundle(repo, env)
    _advance(repo)
    assert _scan(repo, env).returncode == 10
    assert old.exists()
    assert not (exchange / ARCHIVE).exists()


@pytest.mark.parametrize("name", ["/tmp/outside", "../outside", "nested/archive", "C:\\outside", "..", "NUL"])
def test_invalid_archive_cli_keeps_configuration_and_downloads(tmp_path, name):
    env, exchange, repo, _ = _world(tmp_path)
    config_path = user_configuration_path(env)
    before = config_path.read_bytes()
    result = run_cli(repo, "configure", "archive-dir", name, environment_overrides=env)
    assert result.returncode != 0
    assert config_path.read_bytes() == before
    assert not list(exchange.iterdir())


def test_config_migrates_v2_preserving_suffix_and_name_across_setters(tmp_path):
    env, exchange, repo, _ = _world(tmp_path)
    path = user_configuration_path(env)
    path.write_text(json.dumps({"format_version": 2, "exchange_directory": str(exchange), "bundle_suffix": ".txt"}))
    original = path.read_bytes()
    shown = run_cli(repo, "configure", "show", environment_overrides=env)
    assert "archive_directory: PatchHarbor-Archive" in shown.stdout
    assert path.read_bytes() == original
    assert run_cli(repo, "configure", "archive-dir", ".Archive", environment_overrides=env).returncode == 0
    document = json.loads(path.read_bytes())
    assert document["format_version"] == 3
    assert document["bundle_suffix"] == ".txt"
    assert run_cli(repo, "configure", "exchange-directory", str(exchange), environment_overrides=env).returncode == 0
    assert run_cli(repo, "configure", "bundle-suffix", "--clear", environment_overrides=env).returncode == 0
    document = json.loads(path.read_bytes())
    assert document["archive_directory"] == ".Archive"
    assert document["bundle_suffix"] == ""


def test_completed_patch_archives_on_next_scan_and_keeps_current_result(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "patch.zip.txt"
    _committing_patch(package, context)
    raw = package.read_bytes()
    applied = _scan(repo, env)
    assert applied.returncode == 0, applied.stderr + applied.stdout
    record = _identity_record(env, package)
    assert record["apply_status"] == "succeeded"
    assert record["completed_commit"] == git(repo, "rev-parse", "HEAD").stdout.strip()
    results = [path for path in exchange.iterdir() if path.is_file() and path != package]
    assert len(results) == 1
    assert _scan(repo, env).returncode == 10
    assert not package.exists()
    assert (exchange / ARCHIVE / package.name).read_bytes() == raw
    assert results[0].exists()
    # Restoration does not erase the original replay receipt.
    package.write_bytes(raw)
    assert _scan(repo, env).returncode == 10
    assert len(list((exchange / ARCHIVE).iterdir())) == 2
    assert results[0].exists()


def test_explicit_exchange_patch_keeps_explicit_selection_and_records_completion(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "explicit.zip"
    _committing_patch(package, context)
    applied = run_cli(tmp_path, "apply", str(package), "--json", environment_overrides=env)
    assert applied.returncode == 0, applied.stderr + applied.stdout
    assert _identity_record(env, package)["completed_commit"] is not None
    assert _scan(repo, env).returncode == 10
    assert not package.exists()


def test_clean_past_result_archives_but_current_result_is_preserved(tmp_path):
    env, exchange, repo, _ = _world(tmp_path)
    old = _bundle(repo, env)
    old_bytes = old.read_bytes()
    _advance(repo)
    current = _bundle(repo, env)  # bundle is a normal maintenance trigger too
    assert not old.exists()
    assert (exchange / ARCHIVE / old.name).read_bytes() == old_bytes
    assert current.exists()
    _scan(repo, env)
    assert current.exists()


def test_current_and_failed_and_uncommitted_results_are_never_archived(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    current = _bundle(repo, env)
    package = exchange / "failure.zip"
    _write_custom_package(package, context, posix_entrypoint="exit 17", powershell_entrypoint="exit 17")
    assert _scan(repo, env).returncode == 17
    failed_result = next(path for path in exchange.iterdir() if path.is_file() and path not in {current, package})
    (repo / "uncommitted.txt").write_text("irreplaceable")
    dirty = _bundle(repo, env)
    git(repo, "add", "uncommitted.txt")
    git(repo, "commit", "-m", "later unrelated commit")
    _scan(repo, env)
    assert failed_result.exists()
    assert dirty.exists()
    assert package.exists()
    assert not current.exists()


def test_success_without_commit_and_legacy_success_are_not_commit_proofs(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "no-commit.zip"
    _write_custom_package(package, context, posix_entrypoint="true", powershell_entrypoint="$null = 1")
    assert _scan(repo, env).returncode == 0
    record = _identity_record(env, package)
    assert record["apply_status"] == "succeeded"
    assert record["completed_commit"] is None
    _advance(repo)
    _scan(repo, env)
    assert package.exists()
    state_path = exchange_state_path(env)
    state = json.loads(state_path.read_bytes())
    state["format_version"] = 2
    for entry in state["entries"]:
        entry.pop("completed_commit")
    state_path.write_text(json.dumps(state))
    _scan(repo, env)
    assert package.exists()


def test_manual_scope_cannot_archive_another_repository(tmp_path):
    env, exchange, repo_a, _ = _world(tmp_path)
    repo_b = create_repository(tmp_path / "repo-b")
    _register_context(repo_b, env)
    result_b = _bundle(repo_b, env)
    _advance(repo_a)
    _advance(repo_b)
    _scan(repo_a, env)
    assert result_b.exists()
    _scan(tmp_path, env, automatic=True)
    assert not result_b.exists()
    assert (exchange / ARCHIVE / result_b.name).exists()


def test_no_recursion_and_no_foreign_or_corrupt_downloads_moved(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    ordinary = exchange / "normal-download.zip"
    with zipfile.ZipFile(ordinary, "w") as archive:
        archive.writestr("README.txt", "not a PatchHarbor bundle")
    damaged = exchange / "damaged.zip"
    damaged.write_bytes(b"PK\x03\x04broken")
    text = exchange / "file.txt"
    text.write_text("normal download")
    archive_dir = exchange / ARCHIVE
    archive_dir.mkdir()
    nested = archive_dir / "should-not-run.zip"
    _committing_patch(nested, context)
    original_head = context["base_commit"]
    assert _scan(repo, env).returncode == 10
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == original_head
    assert all(path.exists() for path in [ordinary, damaged, text, nested])


@pytest.mark.parametrize("damage", ["hash", "missing", "extra", "dirty", "fingerprint", "context", "run", "duplicate"])
def test_inconsistent_result_is_kept_even_with_ancestor_commit(tmp_path, damage):
    env, exchange, repo, _ = _world(tmp_path)
    result = _bundle(repo, env)
    def mutate(files):
        if damage in {"hash", "missing"}:
            name = next(name for name in files if name.startswith("base/"))
            if damage == "hash":
                files[name] += b"tampered"
            else:
                del files[name]
        elif damage == "extra":
            files["untracked/valuable.txt"] = b"not in metadata"
        elif damage == "dirty":
            files["changes/unstaged.patch"] = b"uncommitted change"
        elif damage == "duplicate":
            files["context.json"] = files["context.json"].replace(b'{', b'{"repo_id":"invalid",', 1)
        else:
            name = {"fingerprint": "manifest.json", "context": "context.json", "run": "logs/run.json"}[damage]
            doc = json.loads(files[name])
            if damage == "run":
                doc["primary_result"]["success"] = False
            else:
                doc["state_fingerprint"] = "a" * 16
            files[name] = json.dumps(doc).encode()
    _rewrite(result, mutate)
    _advance(repo)
    _scan(repo, env)
    assert result.exists()


def test_divergent_or_shallow_or_replaced_git_history_is_not_a_proof(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    _advance(repo, "side")
    side = _bundle(repo, env)
    git(repo, "reset", "--hard", context["base_commit"])
    _advance(repo, "other side")
    _scan(repo, env)
    assert side.exists()
    clean = _bundle(repo, env)
    old_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    _advance(repo, "descendant")
    git_dir = Path(git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
    (git_dir / "shallow").write_text(old_head + "\n")
    _scan(repo, env)
    assert clean.exists()
    (git_dir / "shallow").unlink()
    (git_dir / "info" / "grafts").write_text("")
    _scan(repo, env)
    assert clean.exists()


def test_dry_run_has_no_archive_side_effects(tmp_path):
    env, exchange, repo, _ = _world(tmp_path)
    # Disable while creating a result so the archive directory does not exist.
    run_cli(repo, "configure", "archive-dir", "--clear", environment_overrides=env)
    old = _bundle(repo, env)
    _advance(repo)
    run_cli(repo, "configure", "archive-dir", ARCHIVE, environment_overrides=env)
    assert run_cli(repo, "apply", "--dry-run", "--json", environment_overrides=env).returncode == 10
    assert old.exists()
    assert not (exchange / ARCHIVE).exists()


def test_applicable_patch_is_not_archived_by_age_or_bundle_maintenance(tmp_path):
    import os

    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "ancient.zip.txt"
    _committing_patch(package, context)
    os.utime(package, ns=(1, 1))
    _bundle(repo, env)
    assert package.exists()
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == context["base_commit"]


def test_unknown_repository_result_is_kept_by_global_maintenance(tmp_path):
    env, exchange, repo, _ = _world(tmp_path)
    result = _bundle(repo, env)
    _advance(repo)
    removed = run_cli(tmp_path, "unregister", str(repo), environment_overrides=env)
    assert removed.returncode == 0, removed.stderr
    assert _scan(tmp_path, env, automatic=True).returncode == 10
    assert result.exists()


def test_completion_on_a_different_branch_does_not_allow_archival(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "committed-on-other-branch.zip"
    _committing_patch(package, context)
    assert _scan(repo, env).returncode == 0
    completed = _identity_record(env, package)["completed_commit"]
    assert completed is not None
    git(repo, "reset", "--hard", context["base_commit"])
    _advance(repo, "different descendant, not consumed")
    _scan(repo, env)
    assert package.exists()


def test_legacy_success_loses_no_data_and_invents_no_completion_receipt(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    package = exchange / "legacy-consumed.zip"
    _committing_patch(package, context)
    assert _scan(repo, env).returncode == 0
    assert _identity_record(env, package)["completed_commit"] is not None
    state_path = exchange_state_path(env)
    state = json.loads(state_path.read_bytes())
    state["format_version"] = 2
    for record in state["entries"]:
        record.pop("completed_commit")
    state_path.write_text(json.dumps(state))
    _scan(repo, env)
    assert package.exists()
    assert _identity_record(env, package)["completed_commit"] is None


def test_sha256_repository_supports_real_blob_and_commit_evidence(tmp_path):
    env, exchange = _configure_user(tmp_path)
    repo = create_repository(tmp_path / "sha256-repo", object_format="sha256")
    context = _register_context(repo, env)
    old = _bundle(repo, env)
    package = exchange / "sha256.zip"
    _committing_patch(package, context)
    assert _scan(repo, env).returncode == 0
    assert len(_identity_record(env, package)["completed_commit"]) == 64
    _scan(repo, env)
    assert not package.exists()
    assert not old.exists()
    assert (exchange / ARCHIVE / package.name).exists()
    assert (exchange / ARCHIVE / old.name).exists()


def test_consistent_but_forged_snapshot_tree_is_not_an_archival_proof(tmp_path):
    import hashlib

    env, exchange, repo, _ = _world(tmp_path)
    result = _bundle(repo, env)
    def forge(files):
        manifest = json.loads(files["manifest.json"])
        entry = manifest["base_entries"][0]
        content = b"different valid blob, not the real commit tree\n"
        files["base/" + entry["path"]] = content
        entry["size"] = len(content)
        entry["object_id"] = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        files["manifest.json"] = json.dumps(manifest).encode()
    _rewrite(result, forge)
    _advance(repo)
    _scan(repo, env)
    assert result.exists()


def test_replacement_refs_prevent_an_otherwise_valid_archive_proof(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    old = _bundle(repo, env)
    _advance(repo)
    descendant = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "replace", context["base_commit"], descendant)
    _scan(repo, env)
    assert old.exists()


def test_unavailable_archive_folder_does_not_break_apply_or_lose_bundles(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    (exchange / ARCHIVE).write_bytes(b"unrelated file occupies folder name")
    package = exchange / "valid.zip"
    _committing_patch(package, context)
    assert _scan(repo, env).returncode == 0
    _scan(repo, env)
    assert package.exists()
    assert (exchange / ARCHIVE).read_bytes() == b"unrelated file occupies folder name"
