"""Actual process-death boundaries, ledger persistence and conservative recovery."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from tests.platform_support import project_environment, run_cli
from tests.registration_support import (
    create_repository, exchange_state_path, git, start_repository_lock_holder, release_repository_lock_holder, stop_repository_lock_holder,
)
from tests.test_exchange_archive_e2e import (
    ARCHIVE, _advance, _bundle, _committing_patch, _rewrite, _scan, _world,
)
from tests.test_exchange_e2e import _identity_record, _register_context, _write_custom_package

pytestmark = pytest.mark.e2e

_CRASH = r'''
import os, sys
import patchharbor.application as app
import patchharbor.result_bundle_publication as publication
from patchharbor.cli import main
point = sys.argv[1]
def crash(*args, **kwargs):
    os._exit(86)
if point == "before_entrypoint":
    app.execute_prepared_script_with_log = crash
elif point == "after_commit":
    app._complete_entrypoint_execution = crash
elif point == "before_publish":
    publication.replace_path = crash
elif point == "after_publish":
    app.mark_exchange_apply_finished = crash
elif point == "persistence_error":
    from patchharbor.errors import patch_package_error
    def fail(*args, **kwargs):
        raise patch_package_error("simulated ledger write failure")
    app.mark_exchange_apply_finished = fail
else:
    raise AssertionError(point)
raise SystemExit(main(["apply", "--json", *sys.argv[2:]]))
'''


def _crash(repo, env, point="after_publish", *args):
    result = subprocess.run([sys.executable, "-c", _CRASH, point, *args], cwd=repo,
                            env=project_environment(env), capture_output=True, text=True)
    assert result.returncode == (10 if point == "persistence_error" else 86), result.stdout + result.stderr
    return result


def _pending(tmp_path, *, point="after_publish", explicit=False):
    env, exchange, repo, context = _world(tmp_path)
    patch = exchange / "patch.zip.txt"
    _committing_patch(patch, context)
    _crash(repo, env, point, *([str(patch)] if explicit else []))
    record = _identity_record(env, patch)
    assert record["apply_status"] == "attempted"
    assert record["completed_commit"] is None
    assert record["attempt_run_id"]
    return env, exchange, repo, context, patch, record


def _result(exchange, record):
    for path in exchange.iterdir():
        if path.is_file() and sha256(path.read_bytes()).hexdigest() == record["result_sha256"]:
            return path
    raise AssertionError("pinned result not found")


def _edit_record(env, patch, mutate):
    path = exchange_state_path(env)
    document = json.loads(path.read_bytes())
    for record in document["entries"]:
        if record["path"] == str(patch.resolve()):
            mutate(record)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("trigger", ["manual", "watcher", "bundle"])
def test_real_crash_after_publication_recovers_and_archives(tmp_path, explicit, trigger):
    env, exchange, repo, context, patch, record = _pending(tmp_path, explicit=explicit)
    raw = patch.read_bytes()
    result = _result(exchange, record)
    completed = git(repo, "rev-parse", "HEAD").stdout.strip()
    with zipfile.ZipFile(result) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        run = json.loads(archive.read("logs/run.json"))
    assert manifest["patch_sha256"] == sha256(raw).hexdigest()
    assert manifest["completed_commit"] == completed != context["base_commit"]
    assert manifest["run_id"] == record["attempt_run_id"] == run["run_id"]
    assert run["primary_result"]["success"] is True
    if trigger == "bundle":
        _bundle(repo, env)
    else:
        assert _scan(repo, env, automatic=trigger == "watcher").returncode == 10
    saved = _identity_record(env, patch, sha256(raw).hexdigest())
    assert saved["apply_status"] == "succeeded"
    assert saved["completed_commit"] == completed
    assert not patch.exists()
    assert (exchange / ARCHIVE / patch.name).read_bytes() == raw
    assert result.exists()  # current result is not archived
    # Repeated scans do not rerun the patch or change HEAD.
    assert _scan(repo, env, automatic=True).returncode == 10
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == completed


@pytest.mark.parametrize("point", ["before_entrypoint", "after_commit", "before_publish"])
def test_crash_without_published_success_stays_attempted(tmp_path, point):
    env, exchange, repo, context = _world(tmp_path)
    patch = exchange / "patch.zip"
    _write_custom_package(
        patch, context,
        posix_entrypoint="git add tracked.txt && git commit -qm changed",
        powershell_entrypoint="git add tracked.txt; git commit -qm changed; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        payloads={"tracked.txt": b"patched\n"},
    )
    _crash(repo, env, point)
    record = _identity_record(env, patch)
    before = (repo / "tracked.txt").read_bytes()
    assert before == b"patched\n"
    assert record["apply_status"] == "attempted"
    assert bool(record["result_sha256"]) is (point == "before_publish")
    _scan(repo, env)
    assert _identity_record(env, patch) == record
    assert patch.exists()
    assert (repo / "tracked.txt").read_bytes() == before
    if point == "before_entrypoint":
        assert git(repo, "status", "--porcelain").stdout  # no automatic rollback


def test_ledger_write_error_preserves_the_successful_result_for_recovery(tmp_path):
    env, exchange, repo, _, patch, record = _pending(tmp_path, point="persistence_error")
    result = _result(exchange, record)
    with zipfile.ZipFile(result) as archive:
        assert json.loads(archive.read("logs/run.json"))["primary_result"]["success"] is True
    assert _scan(repo, env).returncode == 10
    assert not patch.exists()
    assert result.exists()


@pytest.mark.parametrize("trigger", ["manual", "watcher", "bundle"])
def test_recovery_works_when_archival_is_disabled(tmp_path, trigger):
    env, exchange, repo, _, patch, record = _pending(tmp_path)
    assert run_cli(repo, "configure", "archive-dir", "--clear", environment_overrides=env).returncode == 0
    if trigger == "bundle":
        _bundle(repo, env)
    else:
        _scan(repo, env, automatic=trigger == "watcher")
    assert _identity_record(env, patch)["apply_status"] == "succeeded"
    assert patch.exists()


def test_active_repository_lock_blocks_recovery_even_for_a_valid_receipt(tmp_path):
    env, exchange, repo, context, patch, record = _pending(tmp_path)
    holder = start_repository_lock_holder(context["repo_id"], environment=project_environment(env))
    try:
        _scan(repo, env, automatic=True)
        assert _identity_record(env, patch) == record
        assert patch.exists()
        assert release_repository_lock_holder(holder) == 0
    finally:
        stop_repository_lock_holder(holder)
    _scan(repo, env, automatic=True)
    assert not patch.exists()


@pytest.mark.parametrize("damage", ["missing-result", "edited-result", "edited-patch", "dirty", "diverged", "missing-run", "missing-digest"])
def test_uncertain_evidence_does_not_repair_or_rollback(tmp_path, damage):
    env, exchange, repo, context, patch, record = _pending(tmp_path)
    result = _result(exchange, record)
    if damage == "missing-result":
        result.unlink()
    elif damage == "edited-result":
        _rewrite(result, lambda files: files.update({"logs/execution.log": b"edited log"}))
    elif damage == "edited-patch":
        _rewrite(patch, lambda files: files.update({"extra.txt": b"edited package"}))
    elif damage == "dirty":
        (repo / "tracked.txt").write_bytes(b"user edits must survive\n")
    elif damage == "diverged":
        git(repo, "checkout", "--detach", context["base_commit"])
        _advance(repo, "unrelated side branch")
    elif damage == "missing-run":
        _edit_record(env, patch, lambda r: r.update(attempt_run_id=None, result_sha256=None))
    else:
        _edit_record(env, patch, lambda r: r.update(result_sha256=None))
    state_path = exchange_state_path(env)
    _scan(repo, env)
    records = json.loads(state_path.read_bytes())["entries"]
    old = next(r for r in records if r["path"] == str(patch.resolve()) and r["sha256"] == record["sha256"])
    assert old["apply_status"] == "attempted"
    assert old["completed_commit"] is None
    assert patch.exists()
    if damage == "dirty":
        assert (repo / "tracked.txt").read_bytes() == b"user edits must survive\n"


@pytest.mark.parametrize("field", ["patch_sha256", "run_id", "repo_id", "expected_base_commit", "expected_state_fingerprint", "completed_commit", "actual_base_commit", "dirty", "base-blob", "duplicate-json"])
def test_semantic_receipt_validation_even_with_inconsistent_local_digest(tmp_path, field):
    env, exchange, repo, _, patch, record = _pending(tmp_path)
    result = _result(exchange, record)
    def mutate(files):
        manifest = json.loads(files["manifest.json"])
        if field == "base-blob":
            key = next(name for name in files if name.startswith("base/"))
            files[key] += b"corrupted"
        elif field == "duplicate-json":
            files["manifest.json"] = files["manifest.json"].replace(b"{", b'{"patch_sha256":"' + b"a"*64 + b'",', 1)
        else:
            manifest[field] = (
                True if field == "dirty" else
                "a"*64 if field == "patch_sha256" else
                "a"*16 if field == "expected_state_fingerprint" else
                "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d" if field in {"repo_id", "run_id"} else
                "a"*40
            )
            files["manifest.json"] = json.dumps(manifest).encode()
    _rewrite(result, mutate)
    # Simulate internally inconsistent persisted state as well as damaged input.
    _edit_record(env, patch, lambda r: r.update(result_sha256=sha256(result.read_bytes()).hexdigest()))
    _scan(repo, env)
    assert _identity_record(env, patch)["apply_status"] == "attempted"
    assert patch.exists() and result.exists()


def test_foreign_scope_cannot_recover_but_global_watcher_can(tmp_path):
    env, exchange, repo_a, _, patch, record = _pending(tmp_path)
    repo_b = create_repository(tmp_path / "repo-b")
    _register_context(repo_b, env)
    _scan(repo_b, env)
    assert _identity_record(env, patch) == record
    _scan(repo_b, env, automatic=True)
    assert not patch.exists()


def test_result_renaming_and_successor_commits_do_not_break_byte_receipt(tmp_path):
    env, exchange, repo, _, patch, record = _pending(tmp_path)
    result = _result(exchange, record)
    renamed = result.with_name("renamed-proof.zip.custom")
    result.rename(renamed)
    _advance(repo)
    _scan(repo, env)
    assert not patch.exists()
    assert (exchange / ARCHIVE / patch.name).exists()
    assert (exchange / ARCHIVE / renamed.name).exists()


def test_dry_run_does_not_recover_pending_attempt(tmp_path):
    env, exchange, repo, _, patch, record = _pending(tmp_path)
    run_cli(repo, "apply", "--dry-run", "--json", environment_overrides=env)
    assert _identity_record(env, patch) == record
    assert patch.exists()


def test_noop_and_failed_entrypoints_do_not_create_a_completion_receipt(tmp_path):
    env, exchange, repo, context = _world(tmp_path)
    for name, posix, windows, expected_code in [("fail", "exit 7", "exit 7", 7), ("noop", "true", "$null = 1", 0)]:
        patch = exchange / (name + ".zip")
        _write_custom_package(patch, context, posix_entrypoint=posix, powershell_entrypoint=windows)
        completed = run_cli(repo, "apply", str(patch), "--json", environment_overrides=env)
        assert completed.returncode == expected_code, completed.stdout + completed.stderr
        record = _identity_record(env, patch)
        assert record["completed_commit"] is None and record["result_sha256"] is None
        result = Path(json.loads(completed.stdout)["result"]["result_bundle"]["path"])
        with zipfile.ZipFile(result) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        assert manifest["patch_sha256"] == sha256(patch.read_bytes()).hexdigest()
        assert manifest["completed_commit"] is None
