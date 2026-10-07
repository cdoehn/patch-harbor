"""Real consumer decisions, including complete historical Format-2 code."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api, result_bundle_publication as publication
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from scripts import runtime_bootstrap
from tests.platform_support import project_environment, run_cli
from tests.result_pyz_support import attach_pyz
from tests.test_reference_validation import edit_document, write_reference
from tests.test_result_format3 import canonical, format3
from tests.test_result_robustness import legacy_source


@pytest.fixture(scope='module')
def format2_source(tmp_path_factory):
    fixture = Path(__file__).parent / 'fixtures/result_format2'
    provenance = json.loads((fixture/'provenance.json').read_bytes())
    raw = (fixture/provenance['wheel_file']).read_bytes()
    assert len(raw) == provenance['wheel_size']
    assert hashlib.sha256(raw).hexdigest() == provenance['wheel_sha256']
    root = tmp_path_factory.mktemp('complete-frozen-format2')
    # Trusted historical whole-distribution fixture, not a mixed-module runtime.
    inventory = {}
    with ZipFile(BytesIO(raw)) as archive:
        for info in archive.infolist():
            parts = info.filename.split('/')
            assert all(part and part not in ('.', '..') for part in parts)
            assert not info.is_dir() and not info.filename.startswith('/')
            target = root.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(info)
            target.write_bytes(data)
            inventory[info.filename] = hashlib.sha256(data).hexdigest()
    return root, inventory


@pytest.mark.e2e
@pytest.mark.parametrize('reader', ['current', 'frozen_format1', 'frozen_format2'])
@pytest.mark.parametrize('state', ['embedded', 'unavailable', 'corrupt', 'future'])
def test_actual_readers_keep_unproven_format3_and_standalone_pyz(
    canonical, legacy_source, format2_source, tmp_path, reader, state,
):
    from tests.test_exchange_archive_e2e import _world, _bundle, _advance, ARCHIVE
    from tests.registration_support import git
    env, exchange, repo, _ = _world(tmp_path)
    old = _bundle(repo, env)
    with ZipFile(old) as archive:
        files = {name:archive.read(name) for name in archive.namelist()}
    legacy = {name:raw for name,raw in files.items() if not name.startswith('runtime/')}
    edit_document(legacy, 'manifest.json', lambda d:(d.update(format_version=1),d.pop('runtime')))
    edit_document(legacy, 'logs/run.json', lambda d:d.update(warnings=[]))
    write_reference(old, legacy)
    files = attach_pyz(files, None if state == 'unavailable' else canonical)
    if state == 'corrupt': files['runtime/runtime.json'] += b'corrupt'
    elif state == 'future': edit_document(files, 'manifest.json', lambda d:d.update(format_version=4))
    reference = exchange/'new-result-disguised-as-patch.zip';write_reference(reference,files)
    standalone = exchange/'standalone-disguised-as-patch.zip';standalone.write_bytes(canonical)
    before = {path:path.read_bytes() for path in (old,reference,standalone)}
    _advance(repo);head = git(repo,'rev-parse','HEAD').stdout
    if reader != 'current':
        source = legacy_source[0] if reader == 'frozen_format1' else format2_source[0]
        expected = ({'patchharbor/'+Path(row['source_path']).name:row['sha256']
                     for row in legacy_source[1]['files'].values()}
                    if reader == 'frozen_format1' else
                    {name:digest for name,digest in format2_source[1].items()
                     if name in ('patchharbor/result_reader.py','patchharbor/patch_inspection.py','patchharbor/api.py')})
        env = {**env,'PYTHONPATH':str(source)}
        probe = subprocess.run([sys.executable,'-B','-c','''
import hashlib, importlib, json, sys
from pathlib import Path
files = {}
for name in json.loads(sys.argv[1]):
    module = importlib.import_module(name[:-3].replace('/', '.'))
    files[name] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
print(json.dumps(files))
''',json.dumps(expected)],cwd=repo,env=project_environment(env),capture_output=True,text=True)
        assert probe.returncode == 0, probe.stdout+probe.stderr
        assert json.loads(probe.stdout) == expected
    result = run_cli(repo,'apply','--json',environment_overrides=env)
    assert result.returncode == 10, result.stdout+result.stderr
    assert git(repo,'rev-parse','HEAD').stdout == head
    assert not old.exists() and (exchange/ARCHIVE/old.name).read_bytes() == before[old]
    archived = reader == 'current' and state == 'embedded'
    assert reference.exists() is (not archived)
    kept = exchange/ARCHIVE/reference.name if archived else reference
    assert kept.read_bytes() == before[reference]
    assert standalone.read_bytes() == before[standalone]
    assert not (exchange/ARCHIVE/standalone.name).exists()


@pytest.mark.e2e
@pytest.mark.parametrize('state',['embedded','unavailable','corrupt','future'])
def test_real_recovery_requires_full_format3_success(canonical,tmp_path,state):
    from tests.test_exchange_recovery_e2e import _pending, _result, _edit_record
    from tests.test_exchange_archive_e2e import _scan, ARCHIVE
    from tests.test_exchange_e2e import _identity_record
    from tests.registration_support import git
    env,exchange,repo,_,patch,record = _pending(tmp_path)
    result = _result(exchange,record)
    with ZipFile(result) as archive:files={name:archive.read(name) for name in archive.namelist()}
    files=attach_pyz(files,None if state=='unavailable' else canonical)
    if state=='corrupt':files['runtime/runtime.json']+=b'changed'
    elif state=='future':edit_document(files,'manifest.json',lambda d:d.update(format_version=4))
    write_reference(result,files)
    _edit_record(env,patch,lambda row:row.update(result_sha256=hashlib.sha256(result.read_bytes()).hexdigest()))
    head=git(repo,'rev-parse','HEAD').stdout.strip();patch_bytes=patch.read_bytes()
    assert _scan(repo,env,automatic=True).returncode==10
    saved=_identity_record(env,patch,hashlib.sha256(patch_bytes).hexdigest())
    assert saved['apply_status']==('succeeded' if state=='embedded' else 'attempted')
    assert git(repo,'rev-parse','HEAD').stdout.strip()==head and result.exists()
    if state=='embedded':
        assert saved['completed_commit']==head and not patch.exists()
        assert (exchange/ARCHIVE/patch.name).read_bytes()==patch_bytes
    else:assert saved['completed_commit'] is None and patch.read_bytes()==patch_bytes


@pytest.mark.parametrize('status',['embedded','unavailable'])
def test_result3_publication_and_legacy_bootstrap_keep_strict_format_boundaries(canonical,tmp_path,status):
    files,_=format3(canonical if status=='embedded' else None)
    reference=tmp_path/'result.zip';write_reference(reference,files)
    publication._verify_result_bundle(reference,execution_present=False)
    assessment=runtime_bootstrap.assess(reference,trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
    assert assessment.full_reference_valid and assessment.reason=='result_format_requires_pyz_bootstrap'
    assert assessment.wheel_bytes is None and assessment.wheel_name is None
    assert runtime_bootstrap.install(assessment,tmp_path/'not-created').status=='fallback'
    assert not (tmp_path/'not-created').exists()
    files['runtime/runtime.json']+=b' '
    write_reference(reference,files)
    with pytest.raises(api.PatchHarborError) as caught:publication._verify_result_bundle(reference,execution_present=False)
    assert caught.value.reason is api.FailureReason.RESULT_BUNDLE_ERROR


def test_format3_unicode_snapshot_and_standalone_pyz_classification(canonical,tmp_path):
    files,_=format3(canonical)
    name='runtime/Grüße dir/Datei.py'
    files['base/'+name]=files.pop('base/tracked.txt')
    edit_document(files,'manifest.json',lambda d:d['base_entries'][0].update(path=name))
    path=tmp_path/'looks-like-patch.zip';write_reference(path,files)
    assert _classify_content(path,path.read_bytes(),resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.RESULT_BUNDLE
    assert parse_archive_evidence(path.read_bytes(),path).base_entries[0][0]==name
    assert _classify_content(path,canonical,resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.OTHER
