"""Fresh context cannot replace the missing receipt of a crashed Execute."""
from hashlib import sha256
import json

import pytest

from patchharbor.result_reader import read_result_reference
from tests.archive_support import _bundle, _rewrite, _scan
from tests.exchange_support import _identity_record
from tests.recovery_support import _pending, _edit_record
from tests.registration_support import git

pytestmark = [pytest.mark.e2e, pytest.mark.usefixtures('prepared_result_producer')]


@pytest.mark.parametrize('rename_as_result', [False, True])
def test_state_cannot_recover_attempt_even_with_matching_run_and_pinned_digest(tmp_path, rename_as_result):
    env, exchange, repo, _, task, attempt = _pending(tmp_path, point='after_commit')
    state = _bundle(repo, env)
    def same_run(files):
        for name in ('manifest.json', 'logs/run.json', 'environment.json'):
            doc = json.loads(files[name]); doc['run_id'] = attempt['attempt_run_id']
            files[name] = json.dumps(doc).encode()
    _rewrite(state, same_run)
    if rename_as_result:
        state = state.rename(exchange / 'pretend_Result_Bundle.zip')
    facts, digest = read_result_reference(state)
    assert facts.operation == 'bundle' and facts.run_id == attempt['attempt_run_id']
    assert facts.task_sha256 is None and facts.completed_commit is None
    _edit_record(env, task, lambda row: row.update(result_sha256=digest))
    source_before = git(repo, 'rev-parse', 'HEAD').stdout
    task_before, state_before = task.read_bytes(), state.read_bytes()
    assert _scan(repo, env, automatic=True).returncode == 10
    saved = _identity_record(env, task, sha256(task_before).hexdigest())
    assert saved['execute_status'] == 'attempted' and saved['completed_commit'] is None
    assert task.read_bytes() == task_before and state.read_bytes() == state_before
    assert git(repo, 'rev-parse', 'HEAD').stdout == source_before
