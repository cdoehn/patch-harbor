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
from scripts import pyz_bootstrap as bootstrap
from tests.platform_support import project_environment, run_cli
from tests.result_pyz_support import attach_pyz
from tests.reference_support import edit_document, write_reference
from tests.result_pyz_support import canonical, format3




@pytest.mark.e2e
@pytest.mark.parametrize('state', ['embedded', 'unavailable', 'corrupt', 'future'])
def test_actual_readers_keep_unproven_format3_and_standalone_pyz(
    canonical, tmp_path, state,
):
    from tests.archive_support import _world, _bundle, _advance, ARCHIVE
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
    result = run_cli(repo,'apply','--json',environment_overrides=env)
    assert result.returncode == 10, result.stdout+result.stderr
    assert git(repo,'rev-parse','HEAD').stdout == head
    assert old.read_bytes() == before[old] and not (exchange/ARCHIVE/old.name).exists()
    archived = state == 'embedded'
    assert reference.exists() is (not archived)
    kept = exchange/ARCHIVE/reference.name if archived else reference
    assert kept.read_bytes() == before[reference]
    assert standalone.read_bytes() == before[standalone]
    assert not (exchange/ARCHIVE/standalone.name).exists()


@pytest.mark.e2e
@pytest.mark.parametrize('state',['embedded','unavailable','corrupt','future','old1','old2'])
def test_real_recovery_requires_full_format3_success(canonical,tmp_path,state):
    from tests.recovery_support import _pending, _result, _edit_record
    from tests.archive_support import _scan, ARCHIVE
    from tests.exchange_support import _identity_record
    from tests.registration_support import git
    env,exchange,repo,_,patch,record = _pending(tmp_path)
    result = _result(exchange,record)
    with ZipFile(result) as archive:files={name:archive.read(name) for name in archive.namelist()}
    files=attach_pyz(files,None if state=='unavailable' else canonical)
    if state=='corrupt':files['runtime/runtime.json']+=b'changed'
    elif state=='future':edit_document(files,'manifest.json',lambda d:d.update(format_version=4))
    elif state in ('old1','old2'):edit_document(files,'manifest.json',lambda d:d.update(format_version=int(state[-1])))
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
def test_result3_publication_and_bootstrap_keep_strict_format_boundaries(canonical,tmp_path,status):
    files,_=format3(canonical if status=='embedded' else None)
    reference=tmp_path/'result.zip';write_reference(reference,files)
    publication._verify_result_bundle(reference,execution_present=False)
    if status=='embedded':
        assessment=bootstrap.assess(reference,trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
        assert not assessment.full_reference_valid and assessment.pyz_bytes == canonical
    else:
        with pytest.raises(bootstrap.BootstrapUnavailable): bootstrap.assess(reference)
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
