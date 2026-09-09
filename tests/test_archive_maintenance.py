"""Real Git/Exchange proofs, operation-count regressions and last-moment races."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

import patchharbor.archive_git as archive_git
import patchharbor.exchange_archive as maintenance
import patchharbor.platform.archive as platform_archive
import patchharbor.repository_state as repository_state
from patchharbor.configuration import load_configuration
from patchharbor.exchange import scan_exchange_directory
from patchharbor.models import RepositoryId
from patchharbor.user_paths import configuration_user_paths
from tests.platform_support import run_cli
from tests.registration_support import (
    create_repository, exchange_state_path, git, user_configuration_path,
)
from tests.test_exchange_archive_e2e import _world, _bundle, _advance, _committing_patch, _scan, ARCHIVE
from tests.test_exchange_e2e import _register_context


def _inputs(env, exchange, monkeypatch):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    paths = configuration_user_paths()
    configuration = load_configuration(paths)
    artifacts = scan_exchange_directory(exchange, paths=paths)
    return paths, configuration, artifacts


def _maintain(inputs, repo_id):
    paths, configuration, artifacts = inputs
    return maintenance.archive_exchange_artifacts(
        artifacts, configuration=configuration, paths=paths,
        repository_id=RepositoryId(repo_id) if repo_id is not None else None,
    )


def _count_captures(monkeypatch):
    captured = []
    original = repository_state.capture_consistent_repository_snapshot

    def count(repository):
        captured.append(repository.value)
        return original(repository)

    # Both the initial lock/context and the fresh callback must be counted.
    monkeypatch.setattr(repository_state, "capture_consistent_repository_snapshot", count)
    monkeypatch.setattr(maintenance, "capture_consistent_repository_snapshot", count)
    return captured


def test_current_results_share_one_initial_capture_and_need_no_git_ancestry(tmp_path, monkeypatch):
    env, exchange, repo, context = _world(tmp_path)
    current = _bundle(repo, env)
    for number in range(5):
        shutil.copyfile(current, exchange / f"copy-{number}.zip.txt")
    inputs = _inputs(env, exchange, monkeypatch)
    captures = _count_captures(monkeypatch)

    def unexpected(*args):
        pytest.fail("current result is a KEEP decision, not a history query")

    monkeypatch.setattr(archive_git, "require_original_history", unexpected)
    outcome = _maintain(inputs, context["repo_id"])
    assert not outcome.archived
    assert not outcome.warnings
    assert captures == [repo]
    assert all(artifact.path.exists() for artifact in inputs[2])


def test_completed_patch_plus_current_result_uses_initial_and_final_capture_only(tmp_path, monkeypatch):
    env, exchange, repo, context = _world(tmp_path)
    patch = exchange / "completed.zip"
    _committing_patch(patch, context)
    original_bytes = patch.read_bytes()
    assert _scan(repo, env).returncode == 0
    inputs = _inputs(env, exchange, monkeypatch)
    captures = _count_captures(monkeypatch)
    outcome = _maintain(inputs, context["repo_id"])
    assert len(outcome.archived) == 1
    assert outcome.archived[0].read_bytes() == original_bytes
    assert len(outcome.remaining) == 1
    assert outcome.remaining[0].path.exists()
    assert captures == [repo, repo]


def test_each_move_gets_fresh_state_and_history_not_a_cached_authorization(tmp_path, monkeypatch):
    env, exchange, repo, context = _world(tmp_path)
    old = _bundle(repo, env)
    for number in range(2):
        shutil.copyfile(old, exchange / f"old-copy-{number}.zip")
    _advance(repo)
    inputs = _inputs(env, exchange, monkeypatch)
    captures = _count_captures(monkeypatch)
    history_queries = []
    original = archive_git.require_original_history

    def history(repository):
        history_queries.append(repository.value)
        return original(repository)

    monkeypatch.setattr(archive_git, "require_original_history", history)
    outcome = _maintain(inputs, context["repo_id"])
    assert len(outcome.archived) == 3
    assert captures == [repo] * 4  # initial + fresh final for each move
    assert history_queries == [repo] * 6  # initial + fresh final proof per file
    assert not outcome.remaining


@pytest.mark.parametrize("mutation", ["dirty", "head", "grafts", "replace", "config", "identity"])
def test_change_after_final_file_hash_prevents_archival(tmp_path, monkeypatch, mutation):
    env, exchange, repo, context = _world(tmp_path)
    old = _bundle(repo, env)
    original_bytes = old.read_bytes()
    _advance(repo)
    inputs = _inputs(env, exchange, monkeypatch)
    original = platform_archive.read_stable_regular_file_with_sha256
    changed = []

    def after_hash(path, **kwargs):
        snapshot = original(path, **kwargs)
        if path == old and not changed:
            changed.append(mutation)
            if mutation == "dirty":
                (repo / "new-user-file.txt").write_text("must survive")
            elif mutation == "head":
                _advance(repo, "concurrent commit")
            elif mutation == "grafts":
                git_dir = Path(git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
                (git_dir / "info" / "grafts").write_text("")
            elif mutation == "replace":
                head = git(repo, "rev-parse", "HEAD").stdout.strip()
                git(repo, "replace", context["base_commit"], head)
            elif mutation == "identity":
                # Registration is changed without taking PatchHarbor's advisory locks.
                paths = inputs[0]
                document = json.loads(paths.registry_path.read_text())
                document["repositories"] = []
                paths.registry_path.write_text(json.dumps(document))
            else:
                config = user_configuration_path(env)
                doc = json.loads(config.read_text())
                doc["archive_directory"] = ""
                config.write_text(json.dumps(doc))
        return snapshot

    monkeypatch.setattr(platform_archive, "read_stable_regular_file_with_sha256", after_hash)
    outcome = _maintain(inputs, context["repo_id"])
    assert changed == [mutation]
    assert not outcome.archived
    assert old.read_bytes() == original_bytes
    assert not list((exchange / ARCHIVE).iterdir())


def test_replay_receipt_changed_after_hash_prevents_patch_archival(tmp_path, monkeypatch):
    env, exchange, repo, context = _world(tmp_path)
    patch = exchange / "completed.zip"
    _committing_patch(patch, context)
    original_bytes = patch.read_bytes()
    assert _scan(repo, env).returncode == 0
    inputs = _inputs(env, exchange, monkeypatch)
    original = platform_archive.read_stable_regular_file_with_sha256
    changed = []

    def after_hash(path, **kwargs):
        snapshot = original(path, **kwargs)
        if path == patch and not changed:
            changed.append(True)
            state_path = exchange_state_path(env)
            document = json.loads(state_path.read_text())
            for entry in document["entries"]:
                entry["completed_commit"] = None
            state_path.write_text(json.dumps(document))
        return snapshot

    monkeypatch.setattr(platform_archive, "read_stable_regular_file_with_sha256", after_hash)
    outcome = _maintain(inputs, context["repo_id"])
    assert changed == [True]
    assert not outcome.archived
    assert patch.read_bytes() == original_bytes


def test_manual_scope_does_not_capture_foreign_repository_and_global_uses_separate_contexts(tmp_path, monkeypatch):
    env, exchange, repo_a, context_a = _world(tmp_path)
    old_a = _bundle(repo_a, env)
    repo_b = create_repository(tmp_path / "repo-b")
    _register_context(repo_b, env)
    old_b = _bundle(repo_b, env)
    _advance(repo_b)
    inputs = _inputs(env, exchange, monkeypatch)
    captures = _count_captures(monkeypatch)
    manual = _maintain(inputs, context_a["repo_id"])
    assert not manual.archived
    assert captures == [repo_a]
    captures.clear()
    global_result = _maintain(inputs, None)
    assert len(global_result.archived) == 1
    assert old_a.exists() and not old_b.exists()
    assert captures.count(repo_a) == 1
    assert captures.count(repo_b) == 2
