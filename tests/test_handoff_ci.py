"""Read-only manual CI review: complete native evidence, no dispatch or polling."""
from copy import deepcopy
from io import BytesIO
import json
import subprocess
from types import SimpleNamespace
from zipfile import BadZipFile, ZipFile

import pytest
from scripts import run_handoff_ci as ci
from tools.test_results import report_digest
from tools.acceptance_catalog import artifact_names, legacy_proofs

COMMIT = 'a' * 40


def nodes_for(suite, platform):
    nodes = [f'tests/test_probe.py::test_{suite}']
    if suite in ('packaging', 'windows'):
        nodes += [f'tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply[{kind}]' for kind in ('full', 'diff', 'mixed')]
        nodes += [f'tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations[{route}]' for route in ('wheel', 'source', 'sdist')]
        nodes += ['tests/test_packaging_e2e.py::test_release_distributions_run_after_pipx_installation',
                  'tests/test_python_variants.py::test_built_reader_variant_bootstraps_and_packs_in_fresh_stdlib_process[>=3.10]',
                  'tests/test_runtime_bootstrap.py::test_uv_installed_runtime_works_outside_checkout']
    if suite == 'e2e':
        nodes += [f'tests/test_handoff_commit_sequence.py::test_real_diagnostic_and_commit_sequences_keep_gates_and_single_final_push[{n}]' for n in (0, 1, 3)]
    if platform == 'Windows' and suite in ('platform', 'windows'):
        nodes += ['tests/test_python_compat_windows.py::' + name for name in (
            'test_native_legacy_handle_adapter_detects_real_change_with_restored_mtime',
            'test_native_junction_is_rejected_without_new_pathlib_api',
            'test_native_private_request_dacl_is_protected_and_inherited[named]',
            'test_native_private_request_dacl_is_protected_and_inherited[random]')]
        nodes += ['tests/test_bootstrap_python_compat.py::' + name for name in (
            'test_native_bootstrap_detects_same_size_restored_mtime_change',
            'test_native_bootstrap_rejects_junction_parent_without_pathlib_api',
            'test_native_bootstrap_prepares_private_inheriting_dacl')]
    return nodes


def document(nodes, binding):
    result = {'format_version': 1, 'run_id': 'fixture', 'binding': binding, 'mode': 'run',
              'expected_workers': 2, 'started': ['gw0', 'gw1'], 'finished': {}, 'exitstatus': 0,
              'collections': {'gw0': nodes, 'gw1': nodes}, 'collection_reports': [], 'errors': [],
              'reports': [{'nodeid': node, 'when': when, 'outcome': 'passed', 'reason': '',
                           'xfail': False, 'subtest': None, 'worker': 'gw0'}
                          for node in nodes for when in ('setup', 'call', 'teardown')]}
    finish(result)
    return result


def finish(doc):
    for worker in doc['started']:
        rows = [row for row in doc['reports'] if row['worker'] == worker]
        doc['finished'][worker] = {'run_id': doc['run_id'], 'binding': doc['binding'], 'exitstatus': 0,
                                   'collection': doc['collections'][worker], 'collection_reports': [],
                                   'report_count': len(rows), 'reports_sha256': report_digest(rows)}
        if doc['format_version'] == 2:
            doc['finished'][worker]['proofs'] = deepcopy(doc['proofs'])


def encode(files):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for name, data in files.items(): archive.writestr(name, data)
    return output.getvalue()


def reports(name, expected):
    platform, python, engine = expected
    binding = dict(platform=platform, python=python + '.1', windows_engine=engine,
                   source_sha256='b' * 64, pytest='9.1.1', xdist='3.8.0')
    docker = name.startswith('patchharbor-docker-')
    build = dict(format_version=1, commit=COMMIT, commit_source='docker-build-context' if docker else 'checkout',
                 binding=binding, version='1.3.0', requires_python='>=3.10', pyz_content_id='c' * 64,
                 dependencies={n: '1.0' for n in ('pip', 'setuptools', 'build', 'wheel', 'pipx', 'pytest', 'pytest-xdist', 'pytest-timeout', 'tomli')},
                 artifacts=[dict(name='patchharbor-1.3.0' + suffix, size=123, sha256='d' * 64)
                            for suffix in ('-py3-none-any.whl', '.tar.gz', '.pyz')])
    files = {'patchharbor-build.json': json.dumps(build).encode()}
    suites = ('windows',) if engine == 'pwsh' else ('core', 'e2e', 'platform', 'packaging')
    for suite in suites:
        files[f'patchharbor-{suite}-tests.json'] = json.dumps(document(nodes_for(suite, platform), binding)).encode()
    if docker:
        files.update({n: b'complete log' for n in ci.DOCKER_FILES})
        files['summary.txt'] = f'ubuntu_version={name.rsplit("-", 1)[1]}\nstatus=0\nstage=packaging tests\nlog=packaging.log\n'.encode()
    return encode(files)


@pytest.fixture
def github(tmp_path, monkeypatch):
    observed = dict(id=100, head_sha=COMMIT, head_branch='dev', event='workflow_dispatch',
                    workflow_id=77, run_attempt=1, status='completed', conclusion='success',
                    html_url='https://github.com/cdoehn/patch-harbor/actions/runs/100')
    jobs = [dict(id=i+1, name=name, status='completed', conclusion='success', head_sha=COMMIT)
            for i, name in enumerate(sorted(ci.JOBS))]
    artifacts = [dict(id=i+1, name=name, expired=False) for i, name in enumerate(ci.ARTIFACTS)]
    state = SimpleNamespace(run=observed, jobs=jobs, artifacts=artifacts,
        blobs={row['id']: reports(row['name'], ci.ARTIFACTS[row['name']]) for row in artifacts},
        calls=[], fault=None, workspace=tmp_path/'review', reads=0)
    def request(route, body=None, *, binary=False):
        assert body is None and not route.endswith('/dispatches')
        state.calls.append(route)
        if state.fault == 'auth': raise subprocess.CalledProcessError(1, ['gh', 'api'])
        if route == 'actions/workflows/acceptance-tests.yml': return {'id': 77}
        if route == 'actions/runs/100':
            state.reads += 1
            return {**observed, 'head_sha': 'f'*40} if state.fault == 'changed_at_end' and state.reads > 1 else deepcopy(observed)
        if '/jobs?' in route: return {'jobs': deepcopy(jobs)}
        if '/artifacts?' in route: return {'artifacts': deepcopy(artifacts)}
        if route.startswith('actions/artifacts/') and binary: return state.blobs[int(route.split('/')[2])]
        pytest.fail('unexpected network route: ' + route)
    monkeypatch.setattr(ci, 'request', request)
    return state


def test_manual_review_covers_twelve_jobs_and_all_python_artifacts_without_dispatch(github):
    result = ci.run(COMMIT, 100, workspace=github.workspace)
    assert result['status'] == 'success' and result['dispatch_attempts'] == 0
    assert len(result['jobs']) == len(result['artifacts']) == 12
    assert {r['name'] for r in result['artifacts']} == set(ci.ARTIFACTS)
    assert all(r['build']['commit'] == COMMIT and r['reports'] for r in result['artifacts'])
    before = list(github.calls)
    with pytest.raises(FileExistsError): ci.run(COMMIT, 100, workspace=github.workspace)
    assert github.calls == before


@pytest.mark.parametrize('status', ['queued', 'in_progress', 'waiting'])
def test_running_manual_ci_is_recorded_once_without_poll_or_artifact_acceptance(github, status):
    github.run['status'] = status
    result = ci.run(COMMIT, 100, workspace=github.workspace)
    assert result['status'] == 'pending' and result['artifacts'] == [] and result['dispatch_attempts'] == 0
    assert len(github.calls) == 2


@pytest.mark.parametrize('fault', ['auth', 'wrong_sha', 'wrong_branch', 'wrong_workflow', 'wrong_run_id',
    'wrong_event', 'wrong_attempt', 'missing_job', 'wrong_job_sha', 'failed_job', 'failed_run',
    'missing_report', 'expired_report', 'duplicate_report', 'corrupt_report', 'legacy_four_reports', 'changed_at_end'])
def test_manual_ci_failures_preserve_receipt_without_retry(github, fault):
    github.fault = fault
    changes = {'wrong_sha': {'head_sha': 'e'*40}, 'wrong_branch': {'head_branch': 'main'},
               'wrong_workflow': {'workflow_id': 99}, 'wrong_run_id': {'id': 101},
               'wrong_event': {'event': 'push'}, 'wrong_attempt': {'run_attempt': 2},
               'failed_run': {'conclusion': 'failure'}}
    github.run.update(changes.get(fault, {}))
    if fault == 'missing_job': github.jobs.pop()
    if fault == 'wrong_job_sha': github.jobs[0]['head_sha'] = 'e'*40
    if fault == 'failed_job': github.jobs[0]['conclusion'] = 'failure'
    if fault == 'missing_report': github.artifacts.pop()
    if fault == 'expired_report': github.artifacts[0]['expired'] = True
    if fault == 'duplicate_report': github.artifacts.append(deepcopy(github.artifacts[0]))
    if fault == 'corrupt_report': github.blobs[1] = b'not a ZIP'
    if fault == 'legacy_four_reports': github.artifacts[:] = github.artifacts[:4]
    with pytest.raises((ValueError, OSError, BadZipFile, subprocess.SubprocessError)):
        ci.run(COMMIT, 100, workspace=github.workspace)
    saved = json.loads((github.workspace/'evidence.json').read_bytes())
    assert saved['status'] == 'failed' and saved['dispatch_attempts'] == 0
    if fault in changes and fault != 'failed_run':
        assert saved['binding_mismatches'] and not saved['binding_verified']
        assert not any('/jobs?' in r for r in github.calls)


@pytest.mark.parametrize('fault', ['wrong_platform', 'wrong_python', 'missing_pyz_test', 'skip_native',
    'changed_source', 'extra_file', 'serial', 'missing_worker', 'build_commit', 'build_hash', 'build_variant',
    'missing_tomli', 'missing_sdist', 'docker_summary', 'old_python_artifact_name'])
def test_artifact_contract_rejects_incomplete_or_mismatched_proofs(github, fault):
    target = next(row for row in github.artifacts if row['name'] == 'patchharbor-packaging-windows-2025-py3.10')
    if fault == 'docker_summary': target = next(row for row in github.artifacts if row['name'].startswith('patchharbor-docker-'))
    with ZipFile(BytesIO(github.blobs[target['id']])) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    build = json.loads(files['patchharbor-build.json'])
    name = 'patchharbor-platform-tests.json' if fault == 'skip_native' else 'patchharbor-packaging-tests.json'
    doc = json.loads(files[name])
    if fault == 'wrong_platform': doc['binding']['platform'] = 'Linux'
    if fault == 'wrong_python': doc['binding']['python'] = '3.12.1'
    if fault == 'changed_source': doc['binding']['source_sha256'] = 'f'*64
    if fault == 'missing_pyz_test':
        doc = document([n for n in doc['collections']['gw0'] if 'own_instruction' not in n], doc['binding'])
    if fault == 'skip_native':
        row = next(r for r in doc['reports'] if 'native_legacy_handle' in r['nodeid'] and r['when'] == 'call')
        row.update(outcome='skipped', reason='not supported')
    if fault == 'serial':
        doc.update(started=[], finished={}, expected_workers=0, collections={'serial': doc['collections']['gw0']})
        for row in doc['reports']: row['worker'] = 'serial'
    finish(doc)
    if fault == 'missing_worker': doc['finished'].pop('gw1')
    if fault == 'build_commit': build['commit'] = 'b'*40
    if fault == 'build_hash': build['artifacts'][0]['sha256'] = ''
    if fault == 'build_variant': build['requires_python'] = '>=3.12'
    if fault == 'missing_tomli': build['dependencies'].pop('tomli')
    if fault == 'missing_sdist': build['artifacts'].pop(1)
    if fault == 'extra_file': files['foreign.json'] = b'{}'
    if fault == 'docker_summary': files['summary.txt'] = b'status=17\nstage=platform tests\n'
    if fault == 'old_python_artifact_name': target['name'] = 'patchharbor-packaging-windows-2025'
    files['patchharbor-build.json'] = json.dumps(build).encode(); files[name] = json.dumps(doc).encode()
    github.blobs[target['id']] = encode(files)
    with pytest.raises((ValueError, KeyError)): ci.run(COMMIT, 100, workspace=github.workspace)
    assert json.loads((github.workspace/'evidence.json').read_bytes())['status'] == 'failed'


def test_transport_is_get_only_and_refuses_mutation_before_any_subprocess(monkeypatch):
    calls = []
    def invoke(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, b'{"id":100}', b'')
    monkeypatch.setattr(ci.subprocess, 'run', invoke)
    assert ci.request('actions/runs/100') == {'id': 100}
    command, arguments = calls[0]
    assert command[:4] == ['gh', 'api', '--hostname', 'github.com']
    assert command[command.index('--method')+1] == 'GET' and '--input' not in command
    assert arguments['input'] is None and not arguments.get('shell')
    with pytest.raises(ValueError): ci.request('actions/workflows/acceptance-tests.yml/dispatches', {'ref': 'dev'})
    assert len(calls) == 1


@pytest.mark.parametrize('commit,run_id', [('abc', 100), (COMMIT, True), (COMMIT, 0), (COMMIT, '100')])
def test_invalid_machine_identifiers_do_not_create_workspace(github, commit, run_id):
    with pytest.raises(ValueError): ci.run(commit, run_id, workspace=github.workspace)
    assert not github.workspace.exists() and not github.calls


def upgrade_reports(github):
    """Format-2 fixtures deliberately rename every test, retaining only proof IDs."""
    for artifact in github.artifacts:
        with ZipFile(BytesIO(github.blobs[artifact['id']])) as archive:
            files = {n: archive.read(n) for n in archive.namelist()}
        build = json.loads(files['patchharbor-build.json'])
        build.update(format_version=2, test_report_format=2)
        roles = {name: role for role, name in artifact_names(build['version']).items()}
        for row in build['artifacts']:
            row['role'] = roles[row['name']]
        files['patchharbor-build.json'] = json.dumps(build).encode()
        for name in list(files):
            if not name.endswith('-tests.json'):
                continue
            doc = json.loads(files[name])
            original = doc['collections']['gw0']
            rename = {node: f'renamed/{name}.py::check_{i}' for i, node in enumerate(original)}
            doc.update(format_version=2, proofs={rename[node]: proof for node, proof in legacy_proofs(original).items()})
            doc['collections'] = {worker: [rename[node] for node in nodes] for worker, nodes in doc['collections'].items()}
            for row in doc['reports']:
                row['nodeid'] = rename[row['nodeid']]
            finish(doc)
            files[name] = json.dumps(doc).encode()
        github.blobs[artifact['id']] = encode(files)


def test_current_ci_uses_explicit_proofs_after_all_test_paths_and_functions_are_renamed(github):
    upgrade_reports(github)
    result = ci.run(COMMIT, 100, workspace=github.workspace)
    assert result['status'] == 'success' and result['format_version'] == 3
    assert result['dispatch_attempts'] == 0 and len(result['artifacts']) == 12
    for artifact in result['artifacts']:
        assert artifact['proofs'] and artifact['build']['test_report_format'] == 2
        assert all(proof['nodeid'].startswith('renamed/') and proof['test_format'] == 2 for proof in artifact['proofs'])


@pytest.mark.parametrize('fault', ['missing_variant', 'skipped_variant', 'duplicate_variant',
    'wrong_variant', 'unknown_identity', 'outside_collection', 'missing_worker_proofs',
    'different_worker_proofs', 'missing_proofs', 'downgrade', 'build_format', 'artifact_role',
    'wrong_engine', 'duplicate_across_suites'])
def test_current_proof_contract_cannot_hide_missing_cases_or_downgrade_evidence(github, fault):
    upgrade_reports(github)
    target = next(row for row in github.artifacts if row['name'] == 'patchharbor-packaging-windows-2025-py3.10')
    with ZipFile(BytesIO(github.blobs[target['id']])) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    build = json.loads(files['patchharbor-build.json'])
    name = 'patchharbor-packaging-tests.json'
    doc = json.loads(files[name])
    node = next(n for n, proof in doc['proofs'].items() if proof == {'id': 'pyz.own-instruction-apply', 'variant': 'mixed'})
    if fault == 'missing_variant': del doc['proofs'][node]
    if fault == 'skipped_variant':
        next(row for row in doc['reports'] if row['nodeid'] == node and row['when'] == 'call').update(outcome='skipped', reason='not checked')
    if fault == 'duplicate_variant': doc['proofs'][doc['collections']['gw0'][0]] = deepcopy(doc['proofs'][node])
    if fault == 'wrong_variant': doc['proofs'][node]['variant'] = 'only-one-case'
    if fault == 'unknown_identity': doc['proofs'][node]['id'] = 'invented'
    if fault == 'outside_collection': doc['proofs']['not-collected'] = doc['proofs'].pop(node)
    if fault == 'downgrade':
        doc.pop('proofs'); doc['format_version'] = 1
    if fault == 'build_format': build['test_report_format'] = 1
    if fault == 'artifact_role': build['artifacts'][0]['role'] = 'unrelated'
    if fault == 'wrong_engine':
        build['binding']['windows_engine'] = 'pwsh'
        doc['binding']['windows_engine'] = 'pwsh'
    if fault == 'duplicate_across_suites':
        other = json.loads(files['patchharbor-core-tests.json'])
        other['proofs'][other['collections']['gw0'][0]] = deepcopy(doc['proofs'][node])
        finish(other); files['patchharbor-core-tests.json'] = json.dumps(other).encode()
    finish(doc)
    if fault == 'missing_worker_proofs': del doc['finished']['gw1']['proofs']
    if fault == 'different_worker_proofs': doc['finished']['gw1']['proofs'].pop(node)
    if fault == 'missing_proofs': doc.pop('proofs')
    files[name] = json.dumps(doc).encode(); files['patchharbor-build.json'] = json.dumps(build).encode()
    github.blobs[target['id']] = encode(files)
    with pytest.raises(ValueError): ci.run(COMMIT, 100, workspace=github.workspace)
    saved = json.loads((github.workspace/'evidence.json').read_bytes())
    assert saved['status'] == 'failed' and saved['dispatch_attempts'] == 0
