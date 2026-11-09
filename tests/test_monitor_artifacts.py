"""Real packages, full identities and read-only Exchange observations."""
from hashlib import sha256
import json

import pytest

from patchharbor import api
from patchharbor.exchange import classify_exchange_artifact
from patchharbor.exchange_state import ExchangeStateRecord, merge_exchange_classifications, mark_exchange_apply_started, mark_exchange_apply_finished, ExchangeApplyStatus
from patchharbor.monitor_session import result_semantic
from patchharbor.user_paths import registration_user_paths
from tests.test_monitor import registered
from tests.exchange_support import _write_package


def patch(root, context, name='patch.zip'):
    path = root.parent / 'exchange' / name
    _write_package(path, {k: str(getattr(context, k)) for k in
                         ('repo_id', 'base_commit', 'state_fingerprint')})
    return path


def test_patches_match_full_binding_and_replay_without_mutating_state(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    path = patch(root, context)
    result = api.monitor_artifacts(str(root))
    row, = result['artifacts']
    assert row['sha256'] == sha256(path.read_bytes()).hexdigest()
    assert result['selected_candidate'] == str(path)
    paths = registration_user_paths()
    assert not paths.exchange_state_path.exists()
    artifact = classify_exchange_artifact(path)
    merge_exchange_classifications(paths, (ExchangeStateRecord(artifact.identity, artifact.kind.value, artifact.selection),))
    mark_exchange_apply_started(paths, artifact.identity, artifact.selection, verify_identity=lambda: None)
    before = paths.exchange_state_path.read_bytes()
    result = api.monitor_artifacts(str(root))
    assert result['selected_candidate'] is None
    assert result['artifacts'][0]['replay_status'] == 'attempted'
    assert paths.exchange_state_path.read_bytes() == before
    mark_exchange_apply_finished(paths, artifact.identity, artifact.selection, ExchangeApplyStatus.FAILED)
    assert api.monitor_artifacts(str(root))['artifacts'][0]['manual_retry_possible']


def test_shared_exchange_never_selects_other_repository(tmp_path, monkeypatch):
    (a, ac), (b, bc) = registered(tmp_path, monkeypatch, ('one', 'two'))
    ap, bp = patch(a, ac, 'a.zip'), patch(b, bc, 'b.zip')
    result = api.monitor_artifacts(str(a))
    assert result['selected_candidate'] == str(ap)
    assert next(r for r in result['artifacts'] if r['path'] == str(bp))['eligibility'] == 'different repository'
    (a / 'tracked.txt').write_text('dirty')
    result = api.monitor_artifacts(str(a))
    assert result['selected_candidate'] is None
    assert 'mismatch' in next(r for r in result['artifacts'] if r['path'] == str(ap))['eligibility']


def test_native_result_and_log_are_observed_by_full_hash(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    result_path = api.bundle(root).path
    patch(root, context)
    result = api.monitor_artifacts(str(root))
    rows = result['artifacts']
    reference = next(r for r in rows if r['kind'] == 'result_bundle')
    assert reference['repo_id'] == str(context.repo_id)
    assert reference['result_status'] == 'created'
    assert reference['primary_result']['success'] is True
    assert next(r for r in rows if r['kind'] == 'patch_package')['source_candidates'] == [reference['sha256']]
    log = api.monitor_log(result_path, expected_sha256=reference['sha256'])
    assert log['run_id'] == reference['run_id'] and log['text']
    with pytest.raises(ValueError, match='identity changed'):
        api.monitor_log(result_path, expected_sha256='0'*64)


def test_archive_is_opt_in_and_never_an_apply_candidate(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    path = patch(root, context)
    archive = path.parent / 'PatchHarbor-Archive'
    archive.mkdir()
    path.rename(archive / path.name)
    assert not api.monitor_artifacts(str(root))['artifacts']
    result = api.monitor_artifacts(str(root), include_archive=True)
    assert result['artifacts'][0]['archived']
    assert result['selected_candidate'] is None


def test_failed_publication_overrides_green_entrypoint_and_stale_is_unknown():
    row = {'primary_result': {'success': True, 'entrypoint_exit_code': 0}, 'result_status': 'failed'}
    assert result_semantic(row) == 'dirty'
    assert result_semantic({**row, 'stale': True}) == 'unknown'
    assert result_semantic({'primary_result': {'success': False, 'entrypoint_exit_code': 9}}) == 'dirty'
    assert result_semantic({'primary_result': {'success': True, 'entrypoint_exit_code': 0}}) == 'clean'
    assert result_semantic({'replay_status': 'attempted'}) == 'unknown'


def test_corrupt_replay_blocks_candidate_instead_of_assuming_unattempted(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    patch(root, context)
    paths = registration_user_paths()
    paths.exchange_state_path.parent.mkdir(parents=True, exist_ok=True)
    paths.exchange_state_path.write_text('{broken')
    result = api.monitor_artifacts(str(root))
    assert result['errors'] and result['selected_candidate'] is None


def test_once_artifacts_json_uses_native_queries(tmp_path, monkeypatch):
    from io import StringIO
    from patchharbor.cli import main
    (root, context), = registered(tmp_path, monkeypatch)
    patch(root, context)
    stdout, stderr = StringIO(), StringIO()
    code = main(['monitor', '--repo', str(root), '--view', 'bundles', '--once', '--json'],
                stdin=StringIO(), stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue() + stdout.getvalue()
    assert json.loads(stdout.getvalue())['bundle_view']['selected_candidate']
