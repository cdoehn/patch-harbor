"""Adversarial complete Result inputs; mutations target independently produced data."""
from dataclasses import replace
import hashlib
import json
import os
import re
import stat
from zipfile import ZipFile, ZipInfo

import pytest

from patchharbor import api
from patchharbor import result_reader
from patchharbor.platform import filesystem
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_snapshot import read_result_snapshot
from tests.reference_support import reference_entries, write_reference
from tests.snapshot_support import produce_case, result_files, update_json

pytestmark = pytest.mark.e2e


@pytest.fixture
def changed_result(tmp_path,monkeypatch):
    case=produce_case(tmp_path,monkeypatch)
    files,modes=result_files(case.result)
    return case,files,modes


def failure(path,files,modes=(),code=None):
    write_reference(path,files,executable=modes)
    with pytest.raises(api.ResultSnapshotError) as caught:api.read_result_snapshot(path)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR
    if code is not None:assert caught.value.code is code
    return caught.value


@pytest.mark.parametrize('variant',['old_oid','new_oid','offset','count','context','duplicate','truncated','unknown','traversal','mode','compressed','binary_size'])
def test_corrupt_changes_never_return_a_partial_snapshot(changed_result,variant):
    case,files,modes=changed_result
    key='changes/staged.patch';raw=files[key]
    if variant in ('old_oid','new_oid'):
        pattern=rb'index ([0-9a-f]{40})\.\.([0-9a-f]{40})'
        match=next(m for m in re.finditer(pattern,raw) if m[1]!=b'0'*40 and m[2]!=b'0'*40)
        group=1 if variant=='old_oid' else 2
        raw=raw[:match.start(group)]+b'f'*40+raw[match.end(group):]
    elif variant=='offset':
        match=re.search(rb'@@ -(\d+)',raw);start,end=match.span(1)
        raw=raw[:start]+str(int(match[1])+1).encode()+raw[end:]
    elif variant=='count':raw=re.sub(rb'(@@ -\d+,)\d+',rb'\g<1>999',raw,count=1)
    elif variant=='context':
        assert b' line 0\n' in raw;raw=raw.replace(b' line 0\n',b' WRONG CONTEXT\n',1)
    elif variant=='duplicate':raw+=raw
    elif variant=='truncated':raw=raw[:-6]
    elif variant=='unknown':raw=raw.replace(b'index ',b'similarity index ',1)
    elif variant=='traversal':raw=re.sub(rb'diff --git [^\n]+',b'diff --git a/../escape b/../escape',raw,count=1)
    elif variant=='mode':raw=raw.replace(b'new file mode 100644',b'new file mode 120000',1)
    elif variant=='compressed':
        match=re.search(rb'(?:literal|delta) \d+\n([^\n]+)',raw);start,end=match.span(1)
        raw=raw[:start]+raw[start:end-1]+b'!'+raw[end:]
    elif variant=='binary_size':raw=re.sub(rb'(literal|delta) \d+\n',b'literal 300000000\n',raw,count=1)
    assert raw!=files[key]
    files[key]=raw
    failure(case.result,files,modes,api.SnapshotErrorCode.RESOURCE_LIMIT if variant=='binary_size' else None)


@pytest.mark.parametrize('name',['tracked.txt','tracked.txt/child','loose/sub/child'])
def test_untracked_collisions_are_not_last_writer_wins(changed_result,name):
    case,files,modes=changed_result;data=b'collision'
    files['untracked/'+name]=data
    update_json(files,'manifest.json',lambda d:d['untracked_entries'].append({'path':name,'mode':'100644','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}))
    failure(case.result,files,modes,api.SnapshotErrorCode.PATH_COLLISION)


@pytest.mark.parametrize('variant',['duplicate','symlink','directory_payload','special','traversal','bad_base','bad_runtime'])
def test_shared_reader_safety_precedes_snapshot_reconstruction(tmp_path,variant):
    files,_=reference_entries();path=tmp_path/'bad.zip'
    if variant=='bad_base':files['base/tracked.txt']+=b'tampered'
    if variant=='bad_runtime':
        name=next(n for n in files if n.endswith('.pyz'));files[name]+=b'tampered'
    write_reference(path,files)
    if variant=='duplicate':
        with pytest.warns(UserWarning):
            with ZipFile(path,'a') as z:z.writestr('base/tracked.txt',files['base/tracked.txt'])
    elif variant in ('symlink','directory_payload','special','traversal'):
        info=ZipInfo('../escape' if variant=='traversal' else 'untracked/unsafe')
        info.create_system=3
        info.external_attr=({'symlink':stat.S_IFLNK,'directory_payload':stat.S_IFDIR,'special':stat.S_IFIFO,'traversal':stat.S_IFREG}[variant]|0o644)<<16
        with ZipFile(path,'a') as z:z.writestr(info,b'target')
    with pytest.raises(api.ResultSnapshotError) as caught:api.read_result_snapshot(path)
    expected = api.SnapshotErrorCode.PATH_COLLISION if variant in ("traversal", "duplicate") else api.SnapshotErrorCode.INVALID_RESULT
    assert caught.value.code is expected


def test_expected_digest_and_actual_single_capture(tmp_path,monkeypatch):
    files,_=reference_entries();path=tmp_path/'reference.zip';write_reference(path,files)
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    with pytest.raises(api.ResultSnapshotError) as caught:api.read_result_snapshot(path,expected_sha256='0'*64)
    assert caught.value.code is api.SnapshotErrorCode.DIGEST_MISMATCH
    original=result_reader.read_stable_regular_file_with_sha256;reads=[]
    def captured(*args,**kwargs):
        reads.append(args[0]);value=original(*args,**kwargs)
        path.write_bytes(b'replaced after stable capture')
        return value
    monkeypatch.setattr(result_reader,'read_stable_regular_file_with_sha256',captured)
    snapshot=api.read_result_snapshot(path,expected_sha256=digest)
    assert len(reads)==1 and snapshot.sha256==digest
    assert snapshot.effective.files['tracked.txt'].content==files['base/tracked.txt']


def test_actual_file_change_during_read_is_rejected(tmp_path,monkeypatch):
    files,_=reference_entries();path=tmp_path/'reference.zip';write_reference(path,files)
    original=filesystem.capture_descriptor_metadata;calls=[]
    def metadata(fd):
        calls.append(fd)
        if len(calls)==2:
            with path.open('ab') as stream:stream.write(b'changed during read')
        return original(fd)
    monkeypatch.setattr(filesystem,'capture_descriptor_metadata',metadata)
    with pytest.raises(api.ResultSnapshotError) as caught:api.read_result_snapshot(path)
    assert caught.value.code is api.SnapshotErrorCode.INVALID_RESULT
    assert len(calls)==2


def test_archive_and_reconstructed_budgets_are_independent(changed_result):
    case,files,modes=changed_result
    # Tiny outer entry budget exercises the shared reader, without relaxing production limits.
    with pytest.raises(api.ResultSnapshotError) as caught:
        read_result_snapshot(case.result,resource_policy=replace(DEFAULT_RESOURCE_POLICY,max_zip_entries=3))
    assert caught.value.code is api.SnapshotErrorCode.RESOURCE_LIMIT
    # Retained file versions plus both binary directions exceed an otherwise valid outer ZIP budget.
    outer=sum(map(len,files.values()))
    policy=replace(DEFAULT_RESOURCE_POLICY,max_zip_total_bytes=outer)
    with pytest.raises(api.ResultSnapshotError) as caught:read_result_snapshot(case.result,resource_policy=policy)
    assert caught.value.code is api.SnapshotErrorCode.RESOURCE_LIMIT


def test_duplicate_tree_versions_share_unchanged_content(tmp_path):
    files,_=reference_entries();path=tmp_path/'reference.zip';write_reference(path,files)
    snapshot=api.read_result_snapshot(path)
    base=snapshot.base.files['tracked.txt']
    assert all(getattr(snapshot,name).files['tracked.txt'] is base for name in ('index','worktree','effective'))
