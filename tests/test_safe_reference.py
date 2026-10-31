"""Public safe capture never invokes configured project helpers or refreshes the index."""
from dataclasses import replace
import os
from pathlib import Path
import sys
import pytest
from patchharbor import api
from tests.registration_support import git
from tests.safe_reference_support import host, source_bytes, arm_helper

pytestmark=pytest.mark.skipif(not sys.platform.startswith('linux'),reason='safe reference host contract 1 requires Linux')


@pytest.mark.parametrize('operation',['context','prepare','bundle'])
@pytest.mark.parametrize('kind',['clean','smudge','process','textconv','external','fsmonitor','hooks'])
def test_helpers_are_never_executed(tmp_path,monkeypatch,operation,kind):
    repo,exchange,output=host(tmp_path,monkeypatch)
    old_plan=api.prepare_reference_export(repo,output_directory=output)
    calls=arm_helper(tmp_path,repo,kind)
    before=source_bytes(repo)
    if kind in ('clean','smudge','process'):
        with pytest.raises(api.SafeExportError) as caught:
            if operation=='context':api.context(repo,capture_mode='safe')
            elif operation=='prepare':api.prepare_reference_export(repo,output_directory=output)
            else:api.bundle(repo,capture_mode='safe',export_plan=old_plan)
        assert caught.value.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
        assert not list(output.iterdir())
    else:
        if operation=='context':assert api.context(repo,capture_mode='safe').dirty
        elif operation=='prepare':assert api.prepare_reference_export(repo,output_directory=output).context.dirty
        else:
            plan=api.prepare_reference_export(repo,output_directory=output)
            result=api.bundle(repo,capture_mode='safe',export_plan=plan)
            assert api.read_result_snapshot(result.path).effective.files['tracked.txt'].content==b'dirty source bytes\n'
    assert not calls.exists()
    assert source_bytes(repo)==before
    assert not list(exchange.iterdir())


def test_racy_stat_cache_does_not_hide_same_size_changed_bytes(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch)
    git(repo,'update-index','--refresh')
    file=repo/'tracked.txt';metadata=file.stat()
    file.write_bytes(b'next\n');os.utime(file,ns=(metadata.st_atime_ns,metadata.st_mtime_ns))
    before=source_bytes(repo)
    context=api.context(repo,capture_mode='safe')
    assert context.dirty
    plan=api.prepare_reference_export(repo,output_directory=output,expected_context=context)
    result=api.bundle(repo,capture_mode='safe',export_plan=plan)
    snapshot=api.read_result_snapshot(result.path)
    assert snapshot.index.files['tracked.txt'].content==b'base\n'
    assert snapshot.worktree.files['tracked.txt'].content==b'next\n'
    assert source_bytes(repo)==before


def test_capability_and_bad_arguments_do_not_start_production(tmp_path,monkeypatch):
    assert api.integration_capabilities().safe_reference_contract_version==1
    for value in (True,3,None):
        with pytest.raises(TypeError):api.context(tmp_path,capture_mode=value)
        with pytest.raises(TypeError):api.bundle(tmp_path,capture_mode=value)
    for value in ('SAFE','unknown',''):
        with pytest.raises(ValueError):api.context(tmp_path,capture_mode=value)
        with pytest.raises(ValueError):api.bundle(tmp_path,capture_mode=value)
    with pytest.raises(TypeError):api.bundle(tmp_path,capture_mode='safe')
    with pytest.raises(TypeError):api.bundle(tmp_path,capture_mode='safe',export_plan=object())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('origin',['worktree','index','info','global'])
@pytest.mark.parametrize('attribute',['filter=probe','working-tree-encoding=UTF-16','ident'])
def test_conversion_sources_are_rejected_before_helpers(tmp_path,monkeypatch,origin,attribute):
    repo,exchange,output=host(tmp_path,monkeypatch)
    calls=arm_helper(tmp_path,repo,'clean')
    (repo/'.gitattributes').unlink()
    raw=('tracked.txt '+attribute+'\n').encode()
    if origin in ('worktree','index'):
        (repo/'.gitattributes').write_bytes(raw)
        if origin=='index':
            git(repo,'add','.gitattributes')
            (repo/'.gitattributes').write_bytes(b'# worktree differs from index\n')
    elif origin=='info':(repo/'.git/info/attributes').write_bytes(raw)
    else:
        attrs=tmp_path/'global-attributes';attrs.write_bytes(raw)
        config=tmp_path/'global-config';config.write_text('[core]\n attributesFile = '+str(attrs)+'\n')
        monkeypatch.setenv('GIT_CONFIG_GLOBAL',str(config))
    before=source_bytes(repo)
    with pytest.raises(api.SafeExportError) as caught:api.prepare_reference_export(repo,output_directory=output)
    assert caught.value.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
    assert source_bytes(repo)==before and not calls.exists() and not list(output.iterdir())


@pytest.mark.parametrize('attrs,autocrlf,accepted',[
    ('tracked.txt text eol=lf\n','false',False),
    ('tracked.txt -text\n','true',True),
    ('tracked.txt -filter -ident -working-tree-encoding\n','false',True),
    ('','true',False),('','false',True),
])
def test_crlf_and_explicit_unset_attributes_have_defined_semantics(tmp_path,monkeypatch,attrs,autocrlf,accepted):
    repo,exchange,output=host(tmp_path,monkeypatch)
    (repo/'.gitattributes').write_text(attrs)
    git(repo,'add','.gitattributes')
    git(repo,'config','core.autocrlf',autocrlf)
    (repo/'tracked.txt').write_bytes(b'dirty\r\n')
    before=source_bytes(repo)
    if accepted:
        normal=api.context(repo)
        # Normal context may refresh read metadata; the safe call may not.
        before=source_bytes(repo)
        plan=api.prepare_reference_export(repo,output_directory=output)
        assert plan.context==normal
        result=api.bundle(repo,capture_mode='safe',export_plan=plan)
        assert api.read_result_snapshot(result.path).worktree.files['tracked.txt'].content==b'dirty\r\n'
    else:
        with pytest.raises(api.SafeExportError) as caught:api.prepare_reference_export(repo,output_directory=output)
        assert caught.value.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
    assert source_bytes(repo)==before


def test_environment_override_does_not_weaken_conversion_policy(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);calls=arm_helper(tmp_path,repo,'clean')
    monkeypatch.setenv('GIT_CONFIG_COUNT','1');monkeypatch.setenv('GIT_CONFIG_KEY_0','filter.probe.clean')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0','cat')
    before=source_bytes(repo)
    with pytest.raises(api.SafeExportError) as caught:api.context(repo,capture_mode='safe')
    assert caught.value.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
    assert source_bytes(repo)==before and not calls.exists()


def test_partial_clone_is_refused_without_fetch_or_repair(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch)
    helper=tmp_path/'fetch-helper';calls=tmp_path/'fetch-calls'
    helper.write_text('#!/bin/sh\nprintf called > '+str(calls)+'\n');helper.chmod(0o755)
    git(repo,'config','remote.origin.promisor','true')
    git(repo,'config','remote.origin.url','ext::'+str(helper))
    before=source_bytes(repo)
    with pytest.raises(api.SafeExportError) as caught:api.prepare_reference_export(repo,output_directory=output)
    assert caught.value.code is api.SafeExportErrorCode.REPOSITORY
    assert not calls.exists() and source_bytes(repo)==before


def test_conflicting_index_and_worktree_eol_policy_is_refused(tmp_path, monkeypatch):
    repo, _, output = host(tmp_path, monkeypatch)
    (repo / '.gitattributes').write_bytes(b'tracked.txt -text\n')
    git(repo, 'config', 'core.autocrlf', 'true')
    (repo / 'tracked.txt').write_bytes(b'raw\r\n')
    before = source_bytes(repo)
    with pytest.raises(api.SafeExportError) as caught:
        api.prepare_reference_export(repo, output_directory=output)
    assert caught.value.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
    assert source_bytes(repo) == before


@pytest.mark.parametrize('flag', ['--assume-unchanged', '--skip-worktree'])
def test_untrusted_index_flags_remain_explicitly_unsupported(tmp_path, monkeypatch, flag):
    repo, _, output = host(tmp_path, monkeypatch)
    git(repo, 'update-index', flag, 'tracked.txt')
    (repo / 'tracked.txt').write_bytes(b'independently observed raw bytes\n')
    before = source_bytes(repo)
    with pytest.raises(api.SafeExportError) as caught:
        api.prepare_reference_export(repo, output_directory=output)
    assert caught.value.code is api.SafeExportErrorCode.REPOSITORY
    assert source_bytes(repo) == before and not list(output.iterdir())
