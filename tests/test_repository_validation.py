"""Real registered repository validation, lock effects and mutation boundaries."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex

import pytest

from patchharbor import api
from patchharbor.exit_status import exit_code_for_error
from patchharbor.locks import repository_lock, registry_lock
from patchharbor.user_paths import registration_user_paths
import patchharbor.repository_state as state
from tests.registration_support import create_repository, set_isolated_user_environment, git
from tests.test_reference_validation import bound_package

pytestmark = pytest.mark.e2e


def world(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch,tmp_path/'user')
    repo=create_repository(tmp_path/'repo');context=api.register(repo)
    patch=tmp_path/'patch.zip'
    bound_package(patch,{k:str(getattr(context,k)) for k in ('repo_id','base_commit','state_fingerprint','fingerprint_algorithm')})
    return repo,patch,context


def files(root):
    return {p.relative_to(root):(p.read_bytes(),p.stat().st_mode) for p in root.rglob('*')
            if p.is_file() and 'locks' not in p.relative_to(root).parts}


@pytest.mark.parametrize('conversion', ['autocrlf', 'text', 'eol'])
def test_checkout_conversion_retains_legacy_context_but_readonly_rejects_ambiguity(
    tmp_path, monkeypatch, conversion,
):
    repo, patch, context = world(tmp_path, monkeypatch)
    if conversion == 'autocrlf':
        git(repo, 'config', 'core.autocrlf', 'true')
    else:
        attribute = 'text' if conversion == 'text' else 'text eol=crlf'
        (repo / '.git/info/attributes').write_text('tracked.txt ' + attribute + '\n')
        if conversion == 'text':
            git(repo, 'config', 'core.eol', 'crlf')
    tracked = repo / 'tracked.txt'
    # Real conversion and index refresh, confined to this disposable fixture.
    tracked.unlink()
    git(repo, 'checkout-index', '--force', '-u', '--', 'tracked.txt')
    assert b'\r\n' in tracked.read_bytes()
    # Normal context keeps the existing Git state-v1 candidate selection.
    assert api.context(repo) == context
    before = files(tmp_path)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, repository=repo)
    assert int(exit_code_for_error(caught.value)) == 13
    assert files(tmp_path) == before


@pytest.mark.parametrize('attribute,content', [
    ('filter=unused', b'changed\n'),
    ('working-tree-encoding=UTF-16', b'\xff\xfechanged'),
    ('ident', b'$Id: expanded identifier $\n'),
])
def test_readonly_content_conversion_is_explicitly_unsupported(
    tmp_path, monkeypatch, attribute, content,
):
    repo, patch, _ = world(tmp_path, monkeypatch)
    (repo / '.git/info/attributes').write_text('tracked.txt ' + attribute + '\n')
    (repo / 'tracked.txt').write_bytes(content)
    before = files(tmp_path)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, repository=repo)
    assert int(exit_code_for_error(caught.value)) == 13
    assert files(tmp_path) == before


def test_dirty_lf_text_keeps_the_same_binding_in_both_capture_modes(tmp_path, monkeypatch):
    repo, patch, _ = world(tmp_path, monkeypatch)
    (repo / '.git/info/attributes').write_text('tracked.txt text eol=lf\n')
    (repo / 'tracked.txt').write_bytes(b'changed plain LF text\n')
    context = api.context(repo)
    assert context.dirty
    bound_package(patch, {key: str(getattr(context, key)) for key in (
        'repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm',
    )})
    assert api.validate_patch(patch, repository=repo).context == context


@pytest.mark.parametrize('outcome',['success','mismatch','unregistered','unsupported','busy'])
def test_validation_preserves_index_registry_config_replay_and_contents(tmp_path,monkeypatch,outcome):
    repo,patch,context=world(tmp_path,monkeypatch)
    paths=registration_user_paths()
    paths.exchange_state_directory.mkdir()
    paths.exchange_state_path.write_bytes(b'untouched replay/attempt sentinel')
    if outcome=='mismatch':(repo/'tracked.txt').write_bytes(b'changed')
    elif outcome=='unregistered':paths.registry_path.write_text('{"format_version":1,"repositories":{}}')
    elif outcome=='unsupported':git(repo,'config','core.sparseCheckout','true')
    before=files(tmp_path)
    @contextmanager
    def maybe_busy():
        if outcome=='busy':
            with repository_lock(paths,context.repo_id):yield
        else:yield
    with maybe_busy():
        if outcome=='success':
            result=api.validate_patch(patch,repository=repo)
            assert result.context==context and result.binding_matches
        else:
            with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository=repo)
            assert int(exit_code_for_error(caught.value))=={'mismatch':9,'unregistered':8,'unsupported':13,'busy':12}[outcome]
    assert files(tmp_path)==before
    # A failed request releases every lock it acquired.
    with registry_lock(paths),repository_lock(paths,context.repo_id):pass


@pytest.mark.parametrize('mutation',['identity','registry','worktree','head'])
def test_changes_during_capture_do_not_return_the_old_context(tmp_path,monkeypatch,mutation):
    repo,patch,context=world(tmp_path,monkeypatch)
    capture=state.capture_repository_snapshot; changed=[]
    def changing(repository, **options):
        snapshot=capture(repository, **options)
        if not changed:
            changed.append(True)
            if mutation=='identity':
                (repo/'.patchharbor/id').write_text('different')
            elif mutation=='registry':
                registration_user_paths().registry_path.write_text('{"format_version":1,"repositories":{}}')
            elif mutation=='worktree':(repo/'tracked.txt').write_bytes(b'concurrent change')
            else:git(repo,'commit','--allow-empty','-m','concurrent head')
        return snapshot
    monkeypatch.setattr(state,'capture_repository_snapshot',changing)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository=repo)
    assert int(exit_code_for_error(caught.value))==8


def test_registry_change_after_snapshot_is_rechecked(tmp_path,monkeypatch):
    repo,patch,_=world(tmp_path,monkeypatch)
    capture=state.capture_consistent_repository_snapshot
    def changed_after_capture(repository, **options):
        snapshot=capture(repository, **options)
        registration_user_paths().registry_path.write_text('{"format_version":1,"repositories":{}}')
        return snapshot
    monkeypatch.setattr(state,'capture_consistent_repository_snapshot',changed_after_capture)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository=repo)
    assert int(exit_code_for_error(caught.value))==8


def test_missing_registration_creates_no_configuration_directory(tmp_path,monkeypatch):
    from tests.registration_support import isolated_user_environment
    env=isolated_user_environment(tmp_path/'user')
    for name,value in env.items():monkeypatch.setenv(name,value)
    repo=create_repository(tmp_path/'repo')
    from tests.test_reference_validation import reference_entries
    _,binding=reference_entries();patch=tmp_path/'patch.zip';bound_package(patch,binding)
    configuration=Path(env['APPDATA'])/'PatchHarbor' if os.name=='nt' else Path(env['XDG_CONFIG_HOME'])/'patchharbor'
    assert not configuration.exists()
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository=repo)
    assert int(exit_code_for_error(caught.value))==8
    assert not configuration.exists() and not (repo/'.patchharbor').exists()


@pytest.mark.skipif(os.name=='nt',reason='POSIX executable helper; Windows uses the same controlled Git overrides')
@pytest.mark.parametrize('changed', [False, True])
def test_read_queries_do_not_start_fsmonitor_filters_textconv_or_hooks(tmp_path,monkeypatch,changed):
    repo,patch,_=world(tmp_path,monkeypatch)
    sentinel=tmp_path/'MUST_NOT_RUN'
    hook=tmp_path/'evil.sh'
    hook.write_text('#!/bin/sh\nprintf invoked >> '+shlex.quote(str(sentinel))+'\nexit 1\n');hook.chmod(0o755)
    for key in ('core.fsmonitor','filter.evil.clean','filter.evil.smudge','diff.evil.textconv','diff.external'):
        git(repo,'config',key,str(hook))
    (repo/'.git/info/attributes').write_text('tracked.txt filter=evil diff=evil\n')
    hooks=tmp_path/'hooks';hooks.mkdir()
    for name in ('post-index-change','pre-commit','post-checkout'):
        p=hooks/name;p.write_bytes(hook.read_bytes());p.chmod(0o755)
    git(repo,'config','core.hooksPath',str(hooks))
    if changed:
        (repo/'tracked.txt').write_bytes(b'changed filtered content\n')
    # Force Git's racy-index content check deterministically, without sleeps.
    # Only the isolated fixture index's timestamp changes; its bytes stay intact.
    metadata = (repo/'tracked.txt').stat()
    index = repo/'.git/index'
    os.utime(index,ns=(index.stat().st_atime_ns,metadata.st_mtime_ns-5_000_000_000))
    import patchharbor.git_commands as commands
    original_run = commands.subprocess.run
    unexpected_queries = []
    def observed_run(command, **kwargs):
        result = original_run(command, **kwargs)
        if sentinel.exists():
            unexpected_queries.append(command[12:])
        return result
    monkeypatch.setattr(commands.subprocess, 'run', observed_run)
    before=files(tmp_path)
    if changed:
        with pytest.raises(api.PatchHarborError) as caught:
            api.validate_patch(patch,repository=repo)
        assert int(exit_code_for_error(caught.value)) == 13
    else:
        assert api.validate_patch(patch,repository=repo).binding_matches
    assert not sentinel.exists(), unexpected_queries
    assert files(tmp_path)==before


def test_validate_does_not_authorize_later_apply_of_changed_state(tmp_path,monkeypatch):
    repo,patch,_=world(tmp_path,monkeypatch)
    assert api.validate_patch(patch,repository=repo).binding_matches
    (repo/'later.txt').write_bytes(b'user change after validation')
    report=api.dry_run(patch,output_directory=tmp_path/'results')
    assert not report.success and report.primary_result.kind is api.PrimaryResultKind.STATE_MISMATCH
    assert not report.primary_result.entrypoint_started
    assert (repo/'later.txt').read_bytes()==b'user change after validation'


def test_repository_option_does_not_substitute_a_different_identity(tmp_path,monkeypatch):
    repo,patch,_=world(tmp_path,monkeypatch)
    other=create_repository(tmp_path/'other');api.register(other)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository=other)
    assert int(exit_code_for_error(caught.value))==9


def test_repository_path_encoding_failure_is_a_controlled_error(tmp_path,monkeypatch):
    _,patch,_=world(tmp_path,monkeypatch)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,repository='bad\ud800path')
    assert int(exit_code_for_error(caught.value))==8
