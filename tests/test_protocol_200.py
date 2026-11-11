"""New protocol boundaries: no aliases, no implicit conversion, real roundtrips."""
from hashlib import sha256
from io import StringIO
import json
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.cli import main
from tests.apply_support import repository
from tests.patch_inspection_support import MANIFEST, write_package
from tests.platform_support import native_python_script, native_value
from tests.reference_support import reference_entries, write_reference
from tests.registration_support import git


@pytest.mark.parametrize('name', [
    'apply', 'apply_guarded', 'apply_next', 'apply_readiness', 'run',
    'pack_patch', 'inspect_patch', 'validate_patch', 'PatchManifest',
    'PatchInspection', 'PatchValidationResult', 'PatchPackResult',
    'PatchAdmission', 'ApplyLock', 'ApplyReadiness', 'AutomaticApplyResult',
])
def test_removed_python_aliases_are_not_exported_or_callable(name):
    assert name not in api.__all__ and not hasattr(api, name)


@pytest.mark.parametrize('fault', [
    'old_filename', 'old_marker', 'old_version', 'future_version', 'boolean_version',
    'mixed_patch', 'mixed_result', 'duplicate_field',
])
def test_invalid_generations_never_reach_repository_or_execution(tmp_path, monkeypatch, fault):
    from patchharbor import application, application_execute
    task = tmp_path / 'renamed_Task_Bundle.zip'
    manifest = dict(MANIFEST)
    if fault == 'old_marker': manifest['marker'] = 'patch-harbor'
    if fault == 'old_version': manifest['format_version'] = 1
    if fault == 'future_version': manifest['format_version'] = 3
    if fault == 'boolean_version': manifest['format_version'] = True
    encoded = json.dumps(manifest).encode()
    if fault == 'duplicate_field':
        encoded = encoded.replace(b'{', b'{"format_version":2,', 1)
    changes = {'task.json': encoded}
    remove = ()
    if fault == 'old_filename':
        changes['patch.json'] = encoded
        remove = ('task.json',)
    if fault == 'mixed_patch': changes['patch.json'] = encoded
    if fault == 'mixed_result': changes['manifest.json'] = b'{"marker":"patch-harbor-result-bundle"}'
    # write_package replaces entries without repairing the invalid manifest.
    write_package(task, changes=changes)
    if remove:
        with ZipFile(task) as archive:
            members = {name: archive.read(name) for name in archive.namelist() if name not in remove}
        with ZipFile(task, 'w') as archive:
            for name, raw in members.items(): archive.writestr(name, raw)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid Task reached execution')
    monkeypatch.setattr(application_execute, 'execute_task_bundle', forbidden)
    for operation in (api.inspect_task, api.validate_task):
        with pytest.raises(api.PatchHarborError): operation(task)
    for command in ('execute', 'apply'):
        stdout = StringIO()
        code = main([command, str(task), '--json'], stdout=stdout, stderr=StringIO())
        result = json.loads(stdout.getvalue())
        assert code != 0 and result['output_version'] == 2 and result['command'] == 'execute'
        assert result['result']['primary_result']['entrypoint_started'] is False
        assert result['result']['repository_resolved'] is False


@pytest.mark.parametrize('version', [1, 2, 3, 5, True])
def test_old_or_future_result_cannot_be_used_to_pack_a_task(tmp_path, version):
    files, _ = reference_entries()
    manifest = json.loads(files['manifest.json'])
    manifest['format_version'] = version
    files['manifest.json'] = json.dumps(manifest).encode()
    reference = tmp_path / 'looks-current_Result_Bundle.zip'
    write_reference(reference, files)
    contents = tmp_path / 'contents'
    contents.mkdir()
    (contents / 'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    output = tmp_path / 'never-published.zip'
    with pytest.raises(api.PatchHarborError):
        api.pack_task(contents, reference_bundle=reference, entrypoint='run.sh', output=output)
    assert not output.exists()
    assert not list(tmp_path.glob('.*.tmp'))


@pytest.mark.e2e
@pytest.mark.parametrize('command', ['execute', 'apply'])
@pytest.mark.parametrize('exit_code,dry_run', [(0, False), (7, False), (0, True)])
def test_result_task_execute_result_roundtrip_keeps_actual_outcome(
    repository, tmp_path, command, exit_code, dry_run,
):
    root, exchange = repository
    before = git(root, 'rev-parse', 'HEAD').stdout.strip()
    reference = api.bundle(root)
    contents = tmp_path / 'contents'
    contents.mkdir()
    entrypoint = native_value('run.sh', 'run.ps1')
    code = "from pathlib import Path\nimport sys\nPath('entrypoint-ran').write_bytes(b'once')\n"
    code += f'sys.exit({exit_code})\n'
    (contents / entrypoint).write_text(native_python_script(code), encoding='utf-8')
    task = api.pack_task(contents, reference_bundle=reference.path, entrypoint=entrypoint,
                         output_directory=exchange)
    assert '_Task_Bundle_' in task.path.name
    output, error = StringIO(), StringIO()
    arguments = [command, str(task.path), '--json']
    if dry_run: arguments.append('--dry-run')
    status = main(arguments, stdout=output, stderr=error)
    document = json.loads(output.getvalue())
    assert status == document['process_exit_code'] == (0 if dry_run else exit_code)
    assert document['output_version'] == 2 and document['command'] == 'execute'
    assert document['success'] is (dry_run or exit_code == 0)
    if command == 'apply': assert error.getvalue()  # notice channel, not wording
    assert (root / 'entrypoint-ran').exists() is (not dry_run)
    result_path = document['result']['result_bundle']['path']
    with ZipFile(result_path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        run = json.loads(archive.read('logs/run.json'))
        environment = json.loads(archive.read('environment.json'))
        assert manifest['format_version'] == 4
        assert manifest['task_sha256'] == sha256(task.path.read_bytes()).hexdigest()
        assert manifest['completed_commit'] is None
        assert run['operation'] == 'execute' and run['dry_run'] is dry_run
        assert environment['format_version'] == 2 and 'Task' in environment['filename_schemas']
        assert ('logs/execution.log' in archive.namelist()) is (not dry_run)
    snapshot = api.read_result_snapshot(result_path)
    assert snapshot.operation == 'execute' and snapshot.dry_run is dry_run
    assert snapshot.primary_result.success is (dry_run or exit_code == 0)
    assert git(root, 'rev-parse', 'HEAD').stdout.strip() == before
    # A failure Result remains an honest next development reference.
    second = api.pack_task(contents, reference_bundle=result_path, entrypoint=entrypoint,
                           output=exchange / 'explicit-name.zip')
    assert second.path.name == 'explicit-name.zip'
    assert api.validate_task(second.path, reference_bundle=result_path).binding_matches
