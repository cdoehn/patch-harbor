"""Current bundle binding and non-execution boundaries; no historical runtimes."""
import json
import pytest
from patchharbor import api
from patchharbor.exit_status import exit_code_for_error

def json_bytes(document):
    return json.dumps(document).encode()

@pytest.mark.parametrize('field,value,code', [
    ('repo_id', '11111111-2222-4333-8444-555555555555', 9),
    ('base_commit', 'a' * 40, 9),
    ('state_fingerprint', 'f' * 16, 9),
    ('fingerprint_algorithm', 'unsupported-future-algorithm', 10),
])
def test_all_four_binding_components_remain_required(tmp_path, field, value, code):
    from tests.reference_support import reference_entries, write_reference
    from tests.task_inspection_support import MANIFEST, write_package
    files, binding = reference_entries()
    reference = tmp_path / 'current-result.zip'
    write_reference(reference, files)
    task = tmp_path / 'task.zip'
    manifest = {**MANIFEST, **binding, field: value}
    write_package(task, changes={'task.json': json_bytes(manifest)})
    with pytest.raises(api.PatchHarborError) as error:
        api.validate_task(task, reference_bundle=reference)
    assert int(exit_code_for_error(error.value)) == code


@pytest.mark.e2e
def test_exchange_leaves_unsupported_artifacts_untouched(tmp_path, monkeypatch):
    from tests.registration_support import create_repository, git, set_isolated_user_environment
    from tests.reference_support import reference_entries, write_reference
    set_isolated_user_environment(monkeypatch, tmp_path / 'user')
    repo = create_repository(tmp_path / 'repository')
    api.register(repo)
    exchange = tmp_path / 'exchange'
    api.configure_exchange_directory(exchange, repository=repo)
    files, _ = reference_entries()
    manifest = json.loads(files['manifest.json'])
    manifest['format_version'] = 0
    files['manifest.json'] = json_bytes(manifest)
    unknown = exchange / 'unsupported-result.zip'
    write_reference(unknown, files)
    stray = exchange / 'unrecognized.zip'
    stray.write_bytes(b'not a task')
    held = {p: p.read_bytes() for p in (unknown, stray)}
    head = git(repo, 'rev-parse', 'HEAD').stdout
    outcome = api.execute_next()
    assert outcome.process_exit_code == 10 and not outcome.primary_result.entrypoint_started
    assert git(repo, 'rev-parse', 'HEAD').stdout == head
    assert not git(repo, 'status', '--porcelain=v1').stdout
    assert all(path.read_bytes() == raw for path, raw in held.items())
