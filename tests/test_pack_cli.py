"""Pack CLI/API parity, stable JSON and separate postpublication output failures."""
from io import StringIO
import hashlib
import json
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest

from patchharbor import api, cli
from patchharbor.exit_status import exit_code_for_reason
from patchharbor.inspection_output import pack_json_result, validation_json_result
from tests.test_pack_api import request_files


def arguments(files, *more):
    contents, reference, output = files
    return ['pack', str(contents), '--reference-bundle', str(reference),
            '--entrypoint', 'run.sh', '--output-dir', str(output), *more]


def invoke(args, stdout=None, stderr=None):
    stdout = StringIO() if stdout is None else stdout
    stderr = StringIO() if stderr is None else stderr
    code = cli.main(args, stdin=StringIO(), stdout=stdout, stderr=stderr)
    return code, stdout, stderr


def test_cli_uses_public_api_once_with_exact_mode_mapping(request_files, monkeypatch):
    seen = []
    class Routed(RuntimeError): pass
    def routed(*a, **k):
        seen.append((a, k)); raise Routed()
    monkeypatch.setattr(api, 'pack_patch', routed)
    with pytest.raises(Routed): invoke(arguments(request_files, '--mode', 'binary=0755', '--json'))
    assert len(seen) == 1
    positional, options = seen[0]
    assert positional == (request_files[0],)
    assert options == {'reference_bundle': request_files[1], 'entrypoint': 'run.sh',
                       'output': None, 'output_directory': request_files[2],
                       'modes': {'binary': 0o755}, 'observer': None}


def test_actual_cli_json_has_complete_reference_validation_and_published_hash(request_files):
    code, stdout, stderr = invoke(arguments(request_files, '--mode', 'binary=0755', '--json'))
    document = json.loads(stdout.getvalue())
    assert code == 0 and stderr.getvalue() == ''
    assert set(document) == {'output_version', 'command', 'success', 'result', 'error', 'process_exit_code'}
    assert document['output_version'] == 2 and document['command'] == 'pack'
    assert document['success'] and document['error'] is None and document['process_exit_code'] == 0
    result = document['result']; path = Path(result['path'])
    assert set(result) == {'path', 'package_id', 'created_at', 'package_sha256', 'package_size',
                           'reference_sha256', 'validation', 'warnings'}
    assert path.is_absolute() and path.is_file()
    assert UUID(result['package_id']).version == 4 and result['created_at'].endswith('Z')
    assert result['package_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['package_size'] == path.stat().st_size
    assert result['reference_sha256'] == hashlib.sha256(request_files[1].read_bytes()).hexdigest()
    validation = result['validation']
    assert validation['scope'] == 'reference' and validation['binding_matches'] is True
    assert validation['checked_at'].endswith('Z') and validation['not_checked']
    fresh = validation_json_result(api.validate_patch(path, reference_bundle=request_files[1]))
    fresh['checked_at'] = validation['checked_at']
    assert validation == fresh
    with ZipFile(path) as archive:
        assert (archive.getinfo('binary').external_attr >> 16) & 0o777 == 0o755


@pytest.mark.parametrize('edit', ['reference', 'entrypoint', 'output', 'both', 'content', 'empty_entrypoint'])
def test_missing_and_conflicting_arguments_are_usage_errors(request_files, edit, monkeypatch):
    args = arguments(request_files)
    if edit in ('reference', 'entrypoint', 'output'):
        flag = {'reference': '--reference-bundle', 'entrypoint': '--entrypoint', 'output': '--output-dir'}[edit]
        index = args.index(flag); del args[index:index+2]
    elif edit == 'both': args += ['--output', str(request_files[2] / 'name.zip.txt')]
    elif edit == 'content': del args[1]
    else: args[args.index('--entrypoint')+1] = ''
    monkeypatch.setattr(api, 'pack_patch', lambda *a, **k: pytest.fail('invalid usage reached API'))
    with pytest.raises(SystemExit) as caught: invoke(args)
    assert caught.value.code == 2


@pytest.mark.parametrize('mode', ['binary=755', 'binary=0o755', 'binary=8888', '=0644',
                                  'binary=-644', 'binary=', 'binary=06440', 'binary= 0644'])
def test_malformed_mode_is_usage_before_api(request_files, mode, monkeypatch):
    monkeypatch.setattr(api, 'pack_patch', lambda *a, **k: pytest.fail('invalid mode reached API'))
    with pytest.raises(SystemExit) as caught: invoke(arguments(request_files, '--mode', mode))
    assert caught.value.code == 2


def test_duplicate_mode_path_is_not_last_value_wins(request_files):
    with pytest.raises(SystemExit) as caught:
        invoke(arguments(request_files, '--mode', 'binary=0644', '--mode', 'binary=0755'))
    assert caught.value.code == 2


@pytest.mark.parametrize('option', ['--repository', '--force', '--overwrite', '--skip-validation',
                                   '--no-validate', '--apply', '--no-handoff', '--repo-id'])
def test_no_unsafe_or_implicit_pack_options(request_files, option):
    with pytest.raises(SystemExit) as caught: invoke(arguments(request_files, option))
    assert caught.value.code == 2


@pytest.mark.parametrize('reason', [api.FailureReason.NO_VALID_SCRIPT, api.FailureReason.SOURCE_ERROR,
    api.FailureReason.INTERPRETER_ERROR, api.FailureReason.PAYLOAD_PREPARATION_ERROR,
    api.FailureReason.STATE_MISMATCH, api.FailureReason.PATCH_PACKAGE_ERROR, api.FailureReason.INTERRUPTED])
def test_error_envelope_preserves_existing_failure_categories(request_files, monkeypatch, reason):
    def refused(*a, **k): raise api.PatchHarborError('controlled shared error', reason)
    monkeypatch.setattr(api, 'pack_patch', refused)
    code, stdout, _ = invoke(arguments(request_files, '--json'))
    document = json.loads(stdout.getvalue())
    assert code == int(exit_code_for_reason(reason)) == document['process_exit_code']
    assert document['output_version'] == 2 and document['command'] == 'pack'
    assert not document['success'] and document['result'] is None
    assert document['error']['patchharbor_error_code'] == code
    assert document['error']['emergency_diagnostics_path'] is None


@pytest.mark.parametrize('mode,reason', [('binary=0777', 4), ('missing=0755', 10), ('../binary=0644', 4)])
def test_formally_valid_modes_keep_semantic_api_errors(request_files, mode, reason):
    code, stdout, _ = invoke(arguments(request_files, '--mode', mode, '--json'))
    assert code == reason == json.loads(stdout.getvalue())['process_exit_code']
    assert not list(request_files[2].iterdir())


@pytest.mark.parametrize('json_output', [False, True])
@pytest.mark.parametrize('stage', ['write', 'flush'])
@pytest.mark.parametrize('failure,expected', [(OSError, 7), (KeyboardInterrupt, 130)])
def test_output_failure_after_publication_never_rebuilds_or_emits_second_envelope(
    request_files, monkeypatch, json_output, stage, failure, expected,
):
    calls = []
    original = api.pack_patch
    def packed(*a, **k):
        result = original(*a, **k); calls.append(result); return result
    monkeypatch.setattr(api, 'pack_patch', packed)
    class BrokenOutput(StringIO):
        writes = 0
        def write(self, text):
            self.writes += 1
            if stage == 'write':
                super().write(text[:8]); raise failure('controlled output failure')
            return super().write(text)
        def flush(self):
            if stage == 'flush': raise failure('controlled output failure')
            super().flush()
    stdout, stderr = BrokenOutput(), StringIO()
    args = arguments(request_files, *(('--json',) if json_output else ()))
    code, _, _ = invoke(args, stdout, stderr)
    assert code == expected and len(calls) == 1
    result = calls[0]
    assert result.path.is_file()
    assert result.package_sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()
    assert set(request_files[2].iterdir()) == {result.path}
    assert str(result.path) in stderr.getvalue() and result.package_sha256 in stderr.getvalue()
    if json_output:
        assert stdout.writes == 1  # No appended result:null error document.
        if stage == 'flush': assert json.loads(stdout.getvalue())['success'] is True


def test_cleanup_warnings_are_full_json_success_without_observer(request_files, monkeypatch):
    original = api.pack_patch
    from dataclasses import replace
    results = []
    def cleanup_warning(*a, **k):
        result = replace(original(*a, **k), warnings=('remaining owned temporary path',))
        results.append(result); return result
    monkeypatch.setattr(api, 'pack_patch', cleanup_warning)
    code, stdout, _ = invoke(arguments(request_files, '--json'))
    document = json.loads(stdout.getvalue())
    assert code == 0 and document['success'] and document['error'] is None
    assert document['result'] == pack_json_result(results[0])


@pytest.mark.packaging
def test_built_distribution_packs_outside_checkout_with_own_pinned_resources(
    request_files, built_result_source, tmp_path,
):
    import os
    import subprocess
    import sys
    import shutil
    from tests.runtime_permissions import readonly_tree
    # Keep permission changes inside this test's own tree, not the shared build.
    installed = tmp_path/'installed'
    shutil.copytree(built_result_source, installed)
    outside = tmp_path/'outside'; outside.mkdir()
    contents, reference, output = request_files
    script = '''
import json, os, socket, subprocess, sys
from pathlib import Path
root=Path(sys.argv.pop(1)).resolve()
sys.path.insert(0,str(root))
import patchharbor
from patchharbor.cli import main
assert Path(patchharbor.__file__).resolve().is_relative_to(root)
def forbidden(*args,**kwargs):raise AssertionError('pack attempted external work')
socket.socket=subprocess.run=subprocess.Popen=forbidden
os.environ['PATH']=''
raise SystemExit(main(sys.argv[1:]))
'''
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    with readonly_tree(installed, owner=tmp_path, environment=env):
        child = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', script, str(installed),
                                *arguments(request_files,'--json')], cwd=outside, env=env,
                               capture_output=True, text=True, timeout=90)
    assert child.returncode == 0, child.stdout+child.stderr
    result = json.loads(child.stdout)['result']
    final = Path(result['path'])
    assert hashlib.sha256(final.read_bytes()).hexdigest() == result['package_sha256']
    assert api.validate_patch(final, reference_bundle=reference).binding_matches


@pytest.mark.e2e
@pytest.mark.parametrize('change_target', [False, True])
def test_packed_payload_uses_regular_apply_and_rechecks_later_repository_state(tmp_path, monkeypatch, change_target):
    from tests.registration_support import create_repository, set_isolated_user_environment
    from tests.platform_support import native_script, native_value
    set_isolated_user_environment(monkeypatch,tmp_path/'user')
    repo = create_repository(tmp_path/'repo')
    api.register(repo)
    exchange = tmp_path/'exchange'
    api.configure_exchange_directory(exchange,repository=repo)
    reference = api.bundle(repo).path
    contents = tmp_path/'contents';contents.mkdir()
    entrypoint = native_value('run.sh','run.ps1')
    (contents/entrypoint).write_text(native_script('test "$(cat payload.txt)" = desired',
                                                 'if ((Get-Content payload.txt -Raw) -ne "desired") { exit 31 }'))
    (contents/'payload.txt').write_bytes(b'desired')
    packed = api.pack_patch(contents,reference_bundle=reference,entrypoint=entrypoint,output_directory=exchange)
    if change_target:(repo/'tracked.txt').write_text('later change\n')
    report = api.apply(packed.path)
    if change_target:
        assert not report.success and report.primary_result.failure_reason is api.FailureReason.STATE_MISMATCH
        assert not report.primary_result.entrypoint_started and not (repo/'payload.txt').exists()
    else:
        assert report.success and report.primary_result.entrypoint_exit_code == 0
        assert (repo/'payload.txt').read_bytes() == b'desired'
        assert not (repo/entrypoint).exists() and not (repo/'PATCHHARBOR_META').exists()
