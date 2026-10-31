"""Current consumers must preserve genuine, immutable 1.4.0 artifact contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from zipfile import ZipFile
import zipimport

import pytest

from patchharbor import api
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.exit_status import exit_code_for_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import capture_result_reference
from tests.compatibility_140_support import (
    BINDING_FIELDS, FIXTURES, PATCH_CASES, PYZ_SHA256, RESULT_CASES, artifact,
    corrupt_reference, json_bytes, prepared_pyz, provenance, result_members,
    rewrite_zip, sha256,
)
from tests.registration_support import create_repository, git


def test_windows_checkout_preserves_byte_pinned_fixture_sources(tmp_path):
    source = Path(__file__).resolve().parents[1]
    names = ('tests/fixtures/compatibility_140/provenance.json',
             'tests/produce_compatibility_140.py')
    expected = {name: (source / name).read_bytes() for name in names}
    repo = create_repository(tmp_path / 'repository', with_commit=False)
    git(repo, 'config', 'core.autocrlf', 'false')
    for name, raw in {**expected, '.gitattributes': (source / '.gitattributes').read_bytes(),
                      'control.txt': b'ordinary text\n'}.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(repo, 'add', '--all')
    checkout = tmp_path / 'windows-checkout'
    checkout.mkdir()
    git(repo, '-c', 'core.autocrlf=true', 'checkout-index', '--all',
        '--prefix=' + checkout.as_posix() + '/')
    assert (checkout / 'control.txt').read_bytes() == b'ordinary text\r\n'
    for name, raw in expected.items():
        assert (checkout / name).read_bytes() == raw, name


def pack_contents(root):
    root.mkdir()
    (root / 'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 23\n')
    (root / 'payload.bin').write_bytes(b'\x00public payload\xff\n')
    return root


@pytest.mark.parametrize('case', RESULT_CASES)
def test_current_reader_preserves_original_reference_and_execution_facts(case):
    path, expected = artifact('result', case)
    captured = capture_result_reference(path)
    facts = captured.facts
    assert captured.sha256 == expected['sha256']
    assert facts.format_version == expected['format_version'] == 3
    assert {key: str(getattr(facts.context, key)) for key in BINDING_FIELDS} == expected['binding']
    assert str(facts.context.base_commit) == expected['after_commit']
    assert facts.context.dirty is expected['dirty']
    assert facts.operation == expected['operation']
    assert facts.dry_run is expected['dry_run']
    assert facts.primary_result.kind.value == expected['primary_kind']
    assert facts.primary_result.entrypoint_exit_code == expected['entrypoint_exit_code']
    assert facts.primary_result.process_exit_code == expected['process_exit_code']
    assert (str(facts.completed_commit) if facts.completed_commit else None) == expected['completed_commit']
    assert facts.patch_sha256 == expected['patch_sha256']
    assert (str(facts.expected.base_commit) if facts.expected else None) == expected['expected_base_commit']
    assert facts.runtime.status == expected['runtime_status']
    if case == 'unavailable':
        assert facts.runtime.reason == 'source_not_prepared' and facts.runtime.artifact is None
        assert facts.warnings
    else:
        assert facts.runtime.artifact.sha256 == PYZ_SHA256
        assert facts.runtime.version == '1.4.0' and facts.runtime.requires_python == '>=3.10'
        assert facts.runtime.result_formats == (1, 2, 3)
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(expected['entries'])
        for name, item in expected['entries'].items():
            raw = archive.read(name)
            assert len(raw) == item['bytes'] and sha256(raw) == item['sha256']
    assert sha256(path.read_bytes()) == expected['sha256']


@pytest.mark.parametrize('case', RESULT_CASES)
def test_current_pack_inspect_validate_use_actual_frozen_binding_without_execution(tmp_path, monkeypatch, case):
    reference, expected = artifact('result', case)
    contents = pack_contents(tmp_path / 'contents')
    def forbidden(*args, **kwargs):
        pytest.fail('static pack/reference work attempted a process or network operation')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    packed = api.pack_patch(contents, reference_bundle=reference, entrypoint='run.sh',
                            output=tmp_path / 'packed.zip', modes={'run.sh': 0o755, 'payload.bin': 0o644})
    checked = api.validate_patch(packed.path, reference_bundle=reference)
    inspected = api.inspect_patch(packed.path)
    assert checked.inspection == inspected and checked.binding_matches is True
    assert checked.scope is api.PatchValidationScope.REFERENCE
    assert packed.reference_sha256 == checked.reference_sha256 == expected['sha256']
    assert {'authenticity', 'execution', 'tests', 'ci', 'replay'} <= set(checked.not_checked)
    assert str(checked.context.base_commit) == expected['after_commit']
    with ZipFile(packed.path) as archive:
        manifest = json.loads(archive.read('patch.json'))
        assert set(manifest) == {*BINDING_FIELDS, 'marker', 'format_version', 'entrypoint'}
        assert manifest['format_version'] == 1 and manifest['marker'] == 'patch-harbor'
        assert {key: manifest[key] for key in BINDING_FIELDS} == expected['binding']
        environment = json.loads(archive.read('PATCHHARBOR_META/environment.json'))
        assert environment['repository_context'] == expected['binding']
        assert archive.read('payload.bin') == b'\x00public payload\xff\n'
        assert archive.getinfo('run.sh').external_attr >> 16 == 0o100755
        assert archive.getinfo('payload.bin').external_attr >> 16 == 0o100644
    assert not packed.warnings
    assert sha256(reference.read_bytes()) == expected['sha256']


@pytest.mark.parametrize('case', PATCH_CASES)
def test_original_patches_retain_payload_modes_and_full_binding(case, monkeypatch):
    path, expected = artifact('patch', case)
    reference = FIXTURES / expected['reference_fixture']
    def forbidden(*args, **kwargs):
        pytest.fail('static reader imported a ZIP runtime or started a process')
    monkeypatch.setattr(zipimport, 'zipimporter', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    inspected = api.inspect_patch(path)
    validated = api.validate_patch(path, reference_bundle=reference)
    assert validated.binding_matches and validated.inspection == inspected
    assert inspected.package_sha256 == expected['sha256']
    assert next(e for e in inspected.entries if e.path == 'run.sh').unix_mode == 0o755
    if case == 'single':
        assert next(e for e in inspected.entries if e.path == 'payload.sh').unix_mode == 0o755
    assert {'execution', 'tests', 'ci', 'authenticity'} <= set(validated.not_checked)


@pytest.mark.parametrize('case', RESULT_CASES)
def test_exchange_and_recovery_evidence_remain_stricter_than_readability(case):
    path, expected = artifact('result', case)
    raw = path.read_bytes()
    classified = _classify_content(path, raw, resource_policy=DEFAULT_RESOURCE_POLICY)
    assert classified.kind is ExchangeArtifactKind.RESULT_BUNDLE
    if expected['archive_eligible']:
        evidence = parse_archive_evidence(raw, path)
        assert str(evidence.selection.base_commit) == expected['after_commit']
        if expected['completed_commit']:
            assert str(evidence.receipt.completed_commit) == expected['completed_commit']
            assert evidence.receipt.patch_sha256 == expected['patch_sha256']
            assert str(evidence.receipt.expected.base_commit) == expected['before_commit']
        else:
            assert evidence.receipt is None
    else:
        with pytest.raises(ValueError):
            parse_archive_evidence(raw, path)


def test_original_partial_progress_and_dirty_snapshot_are_not_clean_success():
    records = provenance()['results']
    assert [len(records[n]['actual_new_commits']) for n in ('diagnostic', 'single', 'multi', 'partial-failure')] == [0, 1, 2, 1]
    failed, dry = records['partial-failure'], records['dry-run']
    assert failed['before_commit'] != failed['after_commit'] and failed['completed_commit'] is None
    assert failed['process_exit_code'] == 7 and failed['dirty'] and not failed['archive_eligible']
    assert dry['before_commit'] == dry['after_commit'] and dry['entrypoint_exit_code'] is None
    dirty = result_members('dirty')
    assert dirty['base/tracked.txt'] == b'partial commit\n'
    assert b'+staged\n' in dirty['changes/staged.patch']
    assert b'+unstaged\n' in dirty['changes/unstaged.patch']
    assert b'delete-me.txt' in dirty['changes/unstaged.patch']
    assert dirty['untracked/untracked.bin'] == b'\x00public\xff\n'
    assert 'base/Grüße.txt' in dirty
    manifest = json.loads(dirty['manifest.json'])
    assert {e['path']: e['git_mode'] for e in manifest['base_entries']}['tool.sh'] == '100755'


@pytest.mark.parametrize('field,value,code', [
    ('repo_id', '11111111-2222-4333-8444-555555555555', 9),
    ('base_commit', 'a' * 40, 9),
    ('state_fingerprint', 'f' * 16, 9),
    ('fingerprint_algorithm', 'unsupported-future-algorithm', 10),
])
def test_all_four_binding_components_remain_required(tmp_path, field, value, code):
    patch, _ = artifact('patch', 'diagnostic')
    reference, _ = artifact('result', 'clean')
    with ZipFile(patch) as archive:
        manifest = json.loads(archive.read('patch.json'))
        environment = json.loads(archive.read('PATCHHARBOR_META/environment.json'))
    manifest[field] = value
    environment['repository_context'][field] = value
    # Keep the handoff consistent to reach the reference/algorithm boundary.
    from patchharbor.chat_instructions import render_chat_handoff
    handoff = render_chat_handoff(environment)
    changes = {'patch.json': json_bytes(manifest), **dict(handoff.entries(patch=True))}
    changed = tmp_path / 'changed.zip'
    rewrite_zip(patch, changed, changes)
    with pytest.raises(api.PatchHarborError) as error:
        api.validate_patch(changed, reference_bundle=reference)
    assert int(exit_code_for_error(error.value)) == code


@pytest.mark.parametrize('fault', ['snapshot', 'future_result', 'future_runtime', 'capabilities', 'runtime_bytes'])
def test_invalid_and_future_copies_never_become_reference_or_success_proofs(tmp_path, fault):
    original, original_facts = artifact('result', 'clean')
    bad = tmp_path / 'future-disguised-as-patch.zip'
    corrupt_reference(original, bad, fault)
    patch, _ = artifact('patch', 'diagnostic')
    with pytest.raises(api.PatchHarborError) as error:
        api.validate_patch(patch, reference_bundle=bad)
    assert int(exit_code_for_error(error.value)) == 4
    with pytest.raises(ValueError):
        parse_archive_evidence(bad.read_bytes(), bad)
    assert _classify_content(bad, bad.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY).kind is not ExchangeArtifactKind.PATCH_PACKAGE
    contents = pack_contents(tmp_path / 'contents')
    output = tmp_path / 'must-not-publish.zip'
    with pytest.raises(api.PatchHarborError) as error:
        api.pack_patch(contents, reference_bundle=bad, entrypoint='run.sh', output=output)
    assert int(exit_code_for_error(error.value)) == 4 and not output.exists()
    assert sha256(original.read_bytes()) == original_facts['sha256']


@pytest.mark.e2e
def test_real_exchange_keeps_frozen_results_and_standalone_pyz_without_apply(tmp_path):
    from tests.registration_support import create_repository, git
    repo = create_repository(tmp_path / 'repository')
    api.register(repo)
    exchange = tmp_path / 'exchange'
    exchange.mkdir()
    api.configure_exchange_directory(exchange, repository=repo)
    held = {}
    for case in RESULT_CASES:
        source, _ = artifact('result', case)
        target = exchange / ('looks-like-patch-' + case + '.zip')
        held[target] = source.read_bytes()
        target.write_bytes(held[target])
    pyz = prepared_pyz(tmp_path / 'runtime')
    standalone = exchange / 'standalone-patch.zip'
    held[standalone] = pyz.read_bytes()
    standalone.write_bytes(held[standalone])
    head = git(repo, 'rev-parse', 'HEAD').stdout
    outcome = api.apply_next()
    assert outcome.process_exit_code == 10 and not outcome.primary_result.entrypoint_started
    assert git(repo, 'rev-parse', 'HEAD').stdout == head
    assert not git(repo, 'status', '--porcelain=v1').stdout
    assert all(path.read_bytes() == raw for path, raw in held.items())


@pytest.mark.e2e
@pytest.mark.parametrize('mode', ['api', 'cli'])
def test_pinned_original_pyz_operates_in_fresh_stdlib_process(tmp_path, mode):
    runtime = prepared_pyz(tmp_path / 'runtime')
    reference, expected = artifact('result', 'clean')
    original_patch, _ = artifact('patch', 'diagnostic')
    contents = pack_contents(tmp_path / 'contents')
    environment = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'PYTHONHOME'}}
    environment['PATH'] = ''
    prefix = [sys.executable, '-I', '-S', '-B']
    if mode == 'cli':
        for arguments in [('inspect', str(original_patch)),
                          ('validate', str(original_patch), '--reference-bundle', str(reference)),
                          ('pack', str(contents), '--reference-bundle', str(reference),
                           '--entrypoint', 'run.sh', '--output', str(tmp_path / 'cli.zip'))]:
            result = subprocess.run([*prefix, str(runtime), *arguments, '--json'], cwd=tmp_path,
                                    env=environment, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            assert json.loads(result.stdout)['success'] is True
        checked = api.validate_patch(tmp_path / 'cli.zip', reference_bundle=reference)
        assert checked.binding_matches and checked.reference_sha256 == expected['sha256']
    else:
        program = '''
import json,os,socket,subprocess,sys
from pathlib import Path
runtime,reference,contents,output=map(Path,sys.argv[1:])
sys.path.insert(0,str(runtime))
import patchharbor
from patchharbor import api
assert patchharbor.__version__=='1.4.0'
assert api.__file__.startswith(str(runtime)+os.sep)
def forbidden(*a,**k):raise AssertionError('offline API crossed process/network boundary')
subprocess.Popen=socket.socket=forbidden
packed=api.pack_patch(contents,reference_bundle=reference,entrypoint='run.sh',output=output)
checked=api.validate_patch(packed.path,reference_bundle=reference)
assert checked.binding_matches and api.inspect_patch(packed.path)==checked.inspection
assert 'patchharbor_watcher' not in sys.modules
print(json.dumps({'reference':checked.reference_sha256,'patch':packed.package_sha256}))
'''
        output = tmp_path / 'api.zip'
        result = subprocess.run([*prefix, '-c', program, str(runtime), str(reference), str(contents), str(output)],
                                cwd=tmp_path, env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        proof = json.loads(result.stdout)
        assert proof['reference'] == expected['sha256'] and proof['patch'] == sha256(output.read_bytes())
        assert api.validate_patch(output, reference_bundle=reference).binding_matches
    assert sha256(runtime.read_bytes()) == PYZ_SHA256


def test_fixture_capture_is_pinned_to_original_release_code_and_generator():
    data = provenance()
    generator = Path(__file__).with_name('produce_compatibility_140.py')
    assert sha256(generator.read_bytes()) == data['generation']['script_sha256']
    assert data['producer']['sha256'] == PYZ_SHA256 and data['producer']['version'] == '1.4.0'
    assert data['producer']['declared_source_commit'] is None
    assert data['unprepared_source']['source_commit'] == '282db1ef5c0af8e2a3ecf41f431f80006487dde4'
    assert data['generation']['archives_rewritten'] is False
    assert len(data['unprepared_source']['files']) == 122
