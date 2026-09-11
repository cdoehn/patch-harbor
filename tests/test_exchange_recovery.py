"""Migration, compare-and-swap and last-moment evidence races."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

import patchharbor.exchange_recovery as recovery
import patchharbor.exchange_state as ledger
from patchharbor.errors import PatchHarborError, patch_package_error
from patchharbor.models import GitObjectId, GitObjectFormat, RepositoryId
from tests.registration_support import git, set_isolated_user_environment, user_configuration_path
from tests.test_archive_maintenance import _inputs
from tests.test_exchange_recovery_e2e import _pending, _result, _edit_record
from tests.test_exchange_e2e import _identity_record
from tests.test_exchange_state import _record, _selection


def _identified_attempt(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    from patchharbor.user_paths import registration_user_paths
    paths = registration_user_paths()
    record = _record(tmp_path / "patch.zip")
    ledger.merge_exchange_classifications(paths, (record,))
    run_id = str(uuid4())
    ledger.mark_exchange_apply_started(paths, record.identity, record.manifest,
                                      verify_identity=lambda: None, run_id=run_id)
    return paths, record, run_id


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_state_reads_without_rewriting_or_inventing_proofs(tmp_path, monkeypatch, version):
    paths, record, _ = _identified_attempt(tmp_path, monkeypatch)
    data = json.loads(paths.exchange_state_path.read_bytes())
    data["format_version"] = version
    for row in data["entries"]:
        row.pop("attempt_run_id")
        row.pop("result_sha256")
        if version < 3:
            row.pop("completed_commit")
        if version == 1:
            row["attempted"] = row.pop("apply_status") is not None
    paths.exchange_state_path.write_text(json.dumps(data), encoding="utf-8")
    before = paths.exchange_state_path.read_bytes()
    restored = ledger.load_exchange_state(paths).record_for(record.identity)
    assert restored.apply_status is ledger.ExchangeApplyStatus.ATTEMPTED
    assert restored.attempt_run_id is None and restored.result_sha256 is None
    assert paths.exchange_state_path.read_bytes() == before
    ledger.merge_exchange_classifications(paths, (_record(tmp_path / "other.zip", "c"),))
    assert json.loads(paths.exchange_state_path.read_bytes())["format_version"] == 4
    restored = ledger.load_exchange_state(paths).record_for(record.identity)
    assert restored.attempt_run_id is None and restored.result_sha256 is None


@pytest.mark.parametrize("field,value", [("attempt_run_id", "not-a-uuid"), ("attempt_run_id", 42),
    ("result_sha256", "a"*63), ("result_sha256", "A"*64), ("result_sha256", True)])
def test_invalid_new_state_fields_are_rejected(tmp_path, monkeypatch, field, value):
    paths, record, _ = _identified_attempt(tmp_path, monkeypatch)
    data = json.loads(paths.exchange_state_path.read_bytes())
    data["entries"][0][field] = value
    paths.exchange_state_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PatchHarborError):
        ledger.load_exchange_state(paths)


def test_result_receipt_cannot_be_reused_for_another_attempt(tmp_path, monkeypatch):
    paths, record, run_id = _identified_attempt(tmp_path, monkeypatch)
    with pytest.raises(PatchHarborError):
        ledger.record_exchange_result_digest(paths, record.identity, record.manifest,
                                            run_id=str(uuid4()), result_sha256="d"*64)
    ledger.record_exchange_result_digest(paths, record.identity, record.manifest,
                                        run_id=run_id, result_sha256="d"*64)
    ledger.mark_exchange_apply_finished(paths, record.identity, record.manifest,
                                       ledger.ExchangeApplyStatus.FAILED, run_id=run_id)
    new_run = str(uuid4())
    ledger.mark_exchange_apply_started(paths, record.identity, record.manifest,
                                      verify_identity=lambda: None, retry_failed=True, run_id=new_run)
    current = ledger.load_exchange_state(paths).record_for(record.identity)
    assert current.attempt_run_id == new_run and current.result_sha256 is None
    with pytest.raises(PatchHarborError):
        ledger.mark_exchange_apply_finished(paths, record.identity, record.manifest,
                                           ledger.ExchangeApplyStatus.SUCCEEDED, run_id=run_id)


def test_recovery_cas_rejects_changed_record_and_failed_final_check(tmp_path, monkeypatch):
    paths, record, run_id = _identified_attempt(tmp_path, monkeypatch)
    ledger.record_exchange_result_digest(paths, record.identity, record.manifest,
                                        run_id=run_id, result_sha256="d"*64)
    expected = ledger.load_exchange_state(paths).record_for(record.identity)
    commit = GitObjectId("e"*40, GitObjectFormat.SHA1)
    def fail():
        raise ValueError("proof changed")
    with pytest.raises(ValueError):
        ledger.recover_exchange_apply_finished(paths, expected, commit, verify_evidence=fail)
    assert ledger.load_exchange_state(paths).record_for(record.identity) == expected
    ledger.mark_exchange_apply_finished(paths, record.identity, record.manifest,
                                       ledger.ExchangeApplyStatus.FAILED, run_id=run_id)
    with pytest.raises(PatchHarborError):
        ledger.recover_exchange_apply_finished(paths, expected, commit, verify_evidence=lambda: None)
    assert ledger.load_exchange_state(paths).record_for(record.identity).apply_status is ledger.ExchangeApplyStatus.FAILED


@pytest.mark.parametrize("mutation", ["dirty", "head", "config", "registry", "patch", "result", "ledger", "grafts", "replace"])
def test_last_moment_change_prevents_recovery(tmp_path, monkeypatch, mutation):
    env, exchange, repo, context, patch, record = _pending(tmp_path)
    result = _result(exchange, record)
    paths, configuration, artifacts = _inputs(env, exchange, monkeypatch)
    original = recovery.recover_exchange_apply_finished
    changed = []
    def race(*args, **kwargs):
        changed.append(True)
        if mutation == "dirty":
            (repo / "user.txt").write_bytes(b"retain me")
        elif mutation == "head":
            git(repo, "commit", "--allow-empty", "-m", "concurrent")
        elif mutation == "config":
            p = user_configuration_path(env)
            d = json.loads(p.read_bytes());d["archive_directory"] = "";p.write_text(json.dumps(d))
        elif mutation == "registry":
            d = json.loads(paths.registry_path.read_bytes());d["repositories"] = []
            paths.registry_path.write_text(json.dumps(d))
        elif mutation in {"patch", "result"}:
            p = patch if mutation == "patch" else result
            p.write_bytes(p.read_bytes() + b"changed")
        elif mutation == "ledger":
            _edit_record(env, patch, lambda r: r.update(result_sha256="a"*64))
        elif mutation == "grafts":
            g = Path(git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
            (g / "info/grafts").write_text("")
        else:
            git(repo, "replace", context["base_commit"], "HEAD")
        return original(*args, **kwargs)
    monkeypatch.setattr(recovery, "recover_exchange_apply_finished", race)
    recovery.recover_exchange_artifacts(artifacts, configuration=configuration, paths=paths,
                                       repository_id=RepositoryId(context["repo_id"]))
    assert changed
    saved = next(r for r in ledger.load_exchange_state(paths).records if r.identity.sha256 == record["sha256"])
    assert saved.apply_status is ledger.ExchangeApplyStatus.ATTEMPTED
    assert saved.completed_commit is None
    assert patch.exists() and result.exists()


def test_state_write_failure_leaves_recovery_repeatable(tmp_path, monkeypatch):
    env, exchange, repo, context, patch, record = _pending(tmp_path)
    paths, configuration, artifacts = _inputs(env, exchange, monkeypatch)
    original = ledger._write_unlocked
    def fail(*args):
        raise patch_package_error("simulated storage failure")
    monkeypatch.setattr(ledger, "_write_unlocked", fail)
    recovery.recover_exchange_artifacts(artifacts, configuration=configuration, paths=paths,
                                       repository_id=RepositoryId(context["repo_id"]))
    assert _identity_record(env, patch) == record
    monkeypatch.setattr(ledger, "_write_unlocked", original)
    recovery.recover_exchange_artifacts(artifacts, configuration=configuration, paths=paths,
                                       repository_id=RepositoryId(context["repo_id"]))
    assert _identity_record(env, patch)["apply_status"] == "succeeded"


def test_out_of_band_ledger_edit_during_verification_is_not_overwritten(tmp_path, monkeypatch):
    paths, record, run_id = _identified_attempt(tmp_path, monkeypatch)
    ledger.record_exchange_result_digest(paths, record.identity, record.manifest,
                                        run_id=run_id, result_sha256="d"*64)
    expected = ledger.load_exchange_state(paths).record_for(record.identity)
    def noncooperative_writer():
        data = json.loads(paths.exchange_state_path.read_bytes())
        data["entries"][0]["result_sha256"] = "e"*64
        paths.exchange_state_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PatchHarborError):
        ledger.recover_exchange_apply_finished(paths, expected, GitObjectId("f"*40, GitObjectFormat.SHA1),
                                              verify_evidence=noncooperative_writer)
    saved = ledger.load_exchange_state(paths).record_for(record.identity)
    assert saved.apply_status is ledger.ExchangeApplyStatus.ATTEMPTED
    assert saved.result_sha256 == "e"*64
