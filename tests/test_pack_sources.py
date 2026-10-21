"""Bounded input capture, real races and the shared static package contracts."""
from dataclasses import replace
import json
from types import SimpleNamespace
import os
from pathlib import Path
import stat
import subprocess

import pytest

from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.pack_sources import capture_sources, resolve_output_target
import patchharbor.pack_sources as sources
import patchharbor.platform.source_tree as tree
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from tests.platform_support import create_symlink_or_skip


SCRIPT=b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n'


@pytest.fixture
def contents(tmp_path):
    root=tmp_path/'contents';root.mkdir()
    (root/'run.sh').write_bytes(SCRIPT)
    return root


def fails(reason, call):
    with pytest.raises(PatchHarborError) as caught:
        call()
    assert caught.value.reason is reason


def test_complete_explicit_tree_preserves_bytes_and_default_modes(contents):
    wanted={'run.sh':SCRIPT,'.gitignore':b'ignored.bin\n','ignored.bin':b'\0\xff\r\n',
            'CHAT_INSTRUCTIONS.md':b'repository document\r\n','sub/file.dat':b'\xfe\0bytes'}
    for name,raw in wanted.items():
        path=contents/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(raw)
    (contents/'empty/deep').mkdir(parents=True)
    if os.name=='posix':
        (contents/'run.sh').chmod(0o777)
    (contents.parent/'neighbor.txt').write_bytes(b'not selected')
    result=capture_sources(contents,'run.sh',modes={'sub/file.dat':0o755})
    assert {p.relative_path:p.content for p in result.files}==wanted
    assert {p.relative_path:p.unix_mode for p in result.files}=={
        name:0o755 if name=='sub/file.dat' else 0o644 for name in wanted}
    assert result.empty_directories==1 and result.warnings
    assert [p.relative_path for p in result.files]==sorted(wanted)
    result.revalidate()


@pytest.mark.parametrize('name',['patch.json','PATCH.JSON','PATCHHARBOR_META','patchharbor_meta','PatchHarbor_Meta'])
def test_reserved_root_inputs_are_not_silently_filtered(contents,name):
    (contents/name).write_bytes(b'{}')
    fails(FailureReason.PATCH_PACKAGE_ERROR,lambda:capture_sources(contents,'run.sh'))


@pytest.mark.parametrize('name',['.git','.patchharbor','nested/.GIT'])
def test_internal_directory_is_rejected_even_when_empty(contents,name):
    (contents/name).mkdir(parents=True)
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


@pytest.mark.parametrize('name',['x y','ä','trailing.','CON','nul.txt','COM1.bin','a'*129])
def test_existing_shared_path_rules_reject_unsafe_source_names(contents,name):
    if os.name=='nt' and name in ('CON','nul.txt','COM1.bin','trailing.'):
        pytest.skip('Windows prevents creating this hostile filesystem name')
    (contents/name).write_bytes(b'x')
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


@pytest.mark.parametrize('entrypoint',['../run.sh','/run.sh','C:/run.sh','a\\run.sh','.git/run.sh'])
def test_unsafe_entrypoint_paths_keep_source_error(contents,entrypoint):
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,entrypoint))


@pytest.mark.parametrize('name',['missing.sh','Run.sh','empty'])
def test_missing_or_directory_entrypoint_keeps_package_error(contents,name):
    (contents/'empty').mkdir()
    fails(FailureReason.PATCH_PACKAGE_ERROR,lambda:capture_sources(contents,name))


@pytest.mark.parametrize('raw',[b'#!/bin/bash\nexit 0\n',b'\xff',b'not a script'])
def test_bad_entrypoint_keeps_shared_script_error(contents,raw):
    (contents/'run.sh').write_bytes(raw)
    fails(FailureReason.NO_VALID_SCRIPT,lambda:capture_sources(contents,'run.sh'))


def test_unsupported_interpreter_keeps_its_existing_category(contents):
    (contents/'run.sh').write_bytes(b'#!/usr/bin/env python\n# PATCHHARBOR\n')
    fails(FailureReason.INTERPRETER_ERROR,lambda:capture_sources(contents,'run.sh'))


def test_static_powershell_selection_does_not_require_an_installed_shell(contents,monkeypatch):
    import patchharbor.interpreters as interpreters
    monkeypatch.setattr(interpreters,'find_executable',lambda *a:pytest.fail('interpreter lookup'))
    raw=b'#!pwsh\r\n# PATCHHARBOR\r\nexit 0\r\n'
    (contents/'run.sh').write_bytes(raw)
    assert capture_sources(contents,'run.sh').files[0].content==raw


@pytest.mark.parametrize('mode',[0o666,0o777,0o1644,0o2644,0o4644,-1,0o10000])
def test_unsafe_requested_modes_keep_source_error(contents,mode):
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh',modes={'run.sh':mode}))


@pytest.mark.parametrize('modes',[{'missing':0o644},{'empty':0o755},{'patch.json':0o644}])
def test_modes_must_name_supplied_regular_files(contents,modes):
    (contents/'empty').mkdir()
    fails(FailureReason.PATCH_PACKAGE_ERROR,lambda:capture_sources(contents,'run.sh',modes=modes))


@pytest.mark.parametrize('modes',[{'run.sh':True},{'run.sh':'0755'},{1:0o644},[]])
def test_pure_argument_type_errors_are_not_tool_errors(contents,modes):
    with pytest.raises(TypeError):capture_sources(contents,'run.sh',modes=modes)


@pytest.mark.parametrize('kind',['file','directory','hardlink'])
def test_source_aliases_are_rejected(contents,tmp_path,kind):
    outside=tmp_path/'outside';outside.mkdir();secret=outside/'secret';secret.write_bytes(b'secret')
    link=contents/'linked'
    if kind=='hardlink':
        try:os.link(secret,link)
        except OSError:pytest.skip('hardlinks unavailable on this filesystem')
    else:create_symlink_or_skip(link,outside if kind=='directory' else secret,target_is_directory=kind=='directory')
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))
    assert secret.read_bytes()==b'secret'


@pytest.mark.skipif(os.name!='posix',reason='POSIX special-file fixture')
@pytest.mark.parametrize('kind',['fifo','socket'])
def test_special_files_are_rejected_without_blocking(contents,kind):
    import socket
    if kind=='fifo':os.mkfifo(contents/'special')
    else:
        with socket.socket(socket.AF_UNIX) as connection:
            try:
                connection.bind(str(contents/'special'))
            except PermissionError:
                pytest.skip('sandbox denies creating a native Unix socket')
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


@pytest.mark.parametrize('kind',[stat.S_IFSOCK,stat.S_IFCHR,stat.S_IFBLK])
def test_special_metadata_is_rejected_before_any_content_open(contents,monkeypatch,kind):
    (contents/'special').write_bytes(b'never read')
    original=tree.SourceDirectory.child_stat
    def metadata(self,name):
        observed=original(self,name)
        if name=='special':
            values=list(observed);values[0]=kind|0o600
            return os.stat_result(values)
        return observed
    monkeypatch.setattr(tree.SourceDirectory,'child_stat',metadata)
    monkeypatch.setattr(tree.SourceDirectory,'read_file',
                        lambda *a,**k:pytest.fail('special file content opened'))
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


def test_case_collisions_are_rejected_before_file_reads(contents,monkeypatch):
    a=contents/'Case';b=contents/'case';a.write_bytes(b'a');b.write_bytes(b'b')
    if os.path.samefile(a,b):pytest.skip('case insensitive filesystem')
    monkeypatch.setattr(tree.SourceDirectory,'read_file',lambda *a,**k:pytest.fail('read before inventory validation'))
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


@pytest.mark.parametrize('limit',['entry','individual','total','scan'])
def test_limits_are_enforced_before_reading_file_contents(contents,monkeypatch,limit):
    (contents/'empty').mkdir()
    policy=DEFAULT_RESOURCE_POLICY
    if limit=='entry':policy=replace(policy,max_zip_entries=3)
    if limit=='individual':policy=replace(policy,warning_bytes=1,max_content_bytes=len(SCRIPT)-1)
    if limit=='total':policy=replace(policy,max_zip_total_bytes=len(SCRIPT)-1)
    if limit=='scan':monkeypatch.setattr(sources,'MAX_SCAN_NODES',2)
    monkeypatch.setattr(tree.SourceDirectory,'read_file',lambda *a,**k:pytest.fail('read before budget validation'))
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh',resource_policy=policy))


def test_exact_file_and_scan_budgets_include_generated_entries_and_directories(contents,monkeypatch):
    (contents/'empty').mkdir();monkeypatch.setattr(sources,'MAX_SCAN_NODES',3)
    result=capture_sources(contents,'run.sh',resource_policy=replace(DEFAULT_RESOURCE_POLICY,max_zip_entries=4))
    assert len(result.files)==1 and result.empty_directories==1


def test_real_thousand_entry_boundary_reserves_all_three_generated_files(contents, monkeypatch):
    for number in range(996):
        (contents / f'payload-{number}').write_bytes(b'')
    policy = replace(DEFAULT_RESOURCE_POLICY, max_zip_entries=1_000)
    captured = capture_sources(contents, 'run.sh', resource_policy=policy)
    assert len(captured.files) + sources.GENERATED_ENTRIES == 1_000
    (contents / 'one-too-many').write_bytes(b'')
    monkeypatch.setattr(tree.SourceDirectory, 'read_file',
                        lambda *a, **k: pytest.fail('over-budget contents read'))
    fails(FailureReason.SOURCE_ERROR, lambda: capture_sources(contents, 'run.sh', resource_policy=policy))


def test_real_ten_thousand_node_boundary_counts_empty_directories(contents, monkeypatch):
    for number in range(9_998):
        (contents / f'empty-{number}').mkdir()
    captured = capture_sources(contents, 'run.sh')
    assert len(captured.inventory) + 1 == 10_000
    assert captured.empty_directories == 9_998
    (contents / 'one-too-many').mkdir()
    monkeypatch.setattr(tree.SourceDirectory, 'read_file',
                        lambda *a, **k: pytest.fail('over-budget contents read'))
    fails(FailureReason.SOURCE_ERROR, lambda: capture_sources(contents, 'run.sh'))


def test_detected_instability_is_not_retried(contents, monkeypatch):
    reads = 0

    def unstable(*args, **kwargs):
        nonlocal reads
        reads += 1
        raise tree.FileChangedDuringRead('controlled pack source mutation')

    monkeypatch.setattr(tree.SourceDirectory, 'read_file', unstable)
    fails(FailureReason.SOURCE_ERROR, lambda: capture_sources(contents, 'run.sh'))
    assert reads == 1


@pytest.mark.parametrize('change',['write','same_size_restored_mtime','replace','delete','add','mode','hardlink'])
def test_final_inventory_revalidation_detects_known_mutation(contents,tmp_path,change):
    result=capture_sources(contents,'run.sh');path=contents/'run.sh'
    if change=='write':path.write_bytes(SCRIPT+b'# edit\n')
    elif change=='same_size_restored_mtime':
        before=path.stat()
        path.write_bytes(SCRIPT.replace(b'exit 0',b'exit 1'))
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
    elif change=='replace':path.unlink();path.write_bytes(SCRIPT)
    elif change=='delete':path.unlink()
    elif change=='add':(contents/'new').write_bytes(b'new')
    elif change=='mode':
        if os.name!='posix':pytest.skip('POSIX permission metadata')
        path.chmod(0o700)
    else:
        try:os.link(path,tmp_path/'alias')
        except OSError:pytest.skip('hardlinks unavailable')
    fails(FailureReason.SOURCE_ERROR,result.revalidate)


@pytest.mark.skipif(os.name!='posix',reason='POSIX controlled ancestor replacement')
def test_directory_swap_cannot_read_outside_root(contents,tmp_path,monkeypatch):
    nested=contents/'nested';nested.mkdir();(nested/'input').write_bytes(b'inside')
    outside=tmp_path/'outside';outside.mkdir();(outside/'input').write_bytes(b'outside')
    original=tree.open_directory_nofollow;swapped=False
    def swap(path,*,parent_fd=None):
        nonlocal swapped
        if path==Path('nested') and not swapped:
            swapped=True;nested.rename(contents/'previous');nested.symlink_to(outside,target_is_directory=True)
        return original(path,parent_fd=parent_fd)
    monkeypatch.setattr(tree,'open_directory_nofollow',swap)
    monkeypatch.setattr(tree.SourceDirectory,'read_file',lambda *a,**k:pytest.fail('escaped inventory boundary'))
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))
    assert swapped and (outside/'input').read_bytes()==b'outside'


@pytest.mark.parametrize('change',['replace','link','add'])
def test_changes_between_scan_and_read_are_rejected(contents,tmp_path,monkeypatch,change):
    original=tree.SourceDirectory.read_file;done=False
    def changed(self,name,expected,*,max_bytes):
        nonlocal done
        if not done:
            done=True
            if change=='replace':(contents/'run.sh').unlink();(contents/'run.sh').write_bytes(SCRIPT)
            elif change=='link':
                outside=tmp_path/'outside';outside.write_bytes(SCRIPT)
                (contents/'run.sh').unlink();create_symlink_or_skip(contents/'run.sh',outside)
            else:(contents/'added').write_bytes(b'added')
        return original(self,name,expected,max_bytes=max_bytes)
    monkeypatch.setattr(tree.SourceDirectory,'read_file',changed)
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))


def test_inflight_write_is_not_a_mixed_success(contents,monkeypatch):
    original=os.read;done=False;identity=(contents/'run.sh').stat()
    def changing(fd,count):
        nonlocal done
        raw=original(fd,count)
        if raw and not done and os.path.samestat(os.fstat(fd),identity):
            done=True
            with (contents/'run.sh').open('ab') as f:f.write(b'# late write\n')
        return raw
    monkeypatch.setattr(tree.os,'read',changing)
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))
    assert done


def test_swap_at_open_cannot_follow_the_replacement(contents,tmp_path,monkeypatch):
    original=tree.open_regular_nofollow;secret=tmp_path/'secret';secret.write_bytes(b'private')
    done=False
    def swap(path,*,parent_fd=None,writable=False):
        nonlocal done
        if not done:
            done=True
            (contents/'run.sh').unlink();create_symlink_or_skip(contents/'run.sh',secret)
        return original(path,parent_fd=parent_fd,writable=writable)
    monkeypatch.setattr(tree,'open_regular_nofollow',swap)
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh'))
    assert done and secret.read_bytes()==b'private'


def test_growth_past_the_observed_budget_is_bounded(contents,monkeypatch):
    original=os.read;done=False;identity=(contents/'run.sh').stat()
    def grow(fd,count):
        nonlocal done
        if not done and os.path.samestat(os.fstat(fd),identity):
            done=True
            with (contents/'run.sh').open('ab') as f:f.write(b'extra')
        return original(fd,count)
    monkeypatch.setattr(tree.os,'read',grow)
    policy=replace(DEFAULT_RESOURCE_POLICY,warning_bytes=1,max_content_bytes=len(SCRIPT))
    fails(FailureReason.SOURCE_ERROR,lambda:capture_sources(contents,'run.sh',resource_policy=policy))
    assert done


def test_root_alias_is_explicitly_resolved_once(contents,tmp_path):
    alias=tmp_path/'root-alias';create_symlink_or_skip(alias,contents,target_is_directory=True)
    result=capture_sources(alias,'run.sh')
    assert result.root==contents.resolve() and result.files[0].content==SCRIPT


@pytest.mark.parametrize('kind',['inside','alias','existing','hardlink','missing_parent'])
def test_output_cannot_alias_inputs_or_replace_files(contents,tmp_path,kind):
    if kind=='inside':output=contents/'output.zip'
    elif kind=='alias':
        alias=tmp_path/'alias';create_symlink_or_skip(alias,contents,target_is_directory=True);output=alias/'output.zip'
    elif kind=='existing':output=tmp_path/'existing.zip';output.write_bytes(b'keep')
    elif kind=='hardlink':
        output=tmp_path/'linked.zip'
        try:os.link(contents/'run.sh',output)
        except OSError:pytest.skip('hardlinks unavailable')
    else:output=tmp_path/'absent'/'output.zip'
    fails(FailureReason.PAYLOAD_PREPARATION_ERROR,lambda:resolve_output_target(output,contents_root=contents.resolve()))
    assert (contents/'run.sh').read_bytes()==SCRIPT


def test_output_resolution_and_capture_are_read_only_without_processes(contents,tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('a process was launched')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    before=sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))
    target=resolve_output_target(tmp_path/'output.zip',contents_root=contents.resolve())
    result=capture_sources(contents,'run.sh')
    result.revalidate()
    assert not target.exists()
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))==before


@pytest.mark.parametrize('field', ['st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
                                  'st_mtime_ns', 'st_ctime_ns', 'st_file_attributes'])
def test_directory_open_mismatch_preserves_safety_and_exact_field_diagnostics(contents, monkeypatch, field):
    child = contents / 'child'; child.mkdir()
    observed = child.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_file_attributes')
    before = SimpleNamespace(**{n: getattr(observed, n, 0) for n in fields})
    values = vars(before).copy()
    values[field] += 0o200 if field == 'st_mode' else 1
    after = SimpleNamespace(**values)
    directory = tree.SourceDirectory(contents, contents.lstat(), None)
    monkeypatch.setattr(tree.SourceDirectory, 'child_stat', lambda *a: before)
    closed = []
    monkeypatch.setattr(tree, 'pin_windows_directory', lambda path: (17, closed.append))
    monkeypatch.setattr(Path, 'lstat', lambda self: after if self == child else observed)
    with pytest.raises(tree.FileChangedDuringRead) as caught:
        with directory.child('child', before): pytest.fail('changed directory admitted')
    assert closed == [17]
    # This JSON is data about the rejected state transition, not display prose.
    delta = json.loads(str(caught.value).split(': ', 1)[1])
    assert delta == {field: {'before': getattr(before, field), 'after': getattr(after, field)}}
    assert caught.value.category == 'unknown'
    assert caught.value.metadata['before']['st_ino'] == before.st_ino


def test_directory_access_time_is_not_a_source_mutation():
    before = SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFDIR | 0o700, st_nlink=1,
                             st_size=0, st_mtime_ns=3, st_ctime_ns=4, st_file_attributes=16, st_atime_ns=5)
    after = SimpleNamespace(**{**vars(before), 'st_atime_ns': 6})
    tree._require_same_directory_metadata(before, after, 'probe')


def _observed_directory(metadata, **changes):
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
              'st_mtime_ns', 'st_ctime_ns', 'st_file_attributes')
    return SimpleNamespace(**{**{n: getattr(metadata, n, 0) for n in fields}, **changes})


@pytest.mark.parametrize('first_attributes', [0x10, 0x10000010])
def test_pack_capture_accepts_windows_directory_attribute_representation_changes(contents, monkeypatch, first_attributes):
    nested = contents / 'nested'; nested.mkdir()
    (nested / 'empty').mkdir()
    (nested / 'data.bin').write_bytes(b'\x00\xffunchanged')
    original = Path.lstat
    observations = {}
    opened, closed = [], []

    def observe(path):
        metadata = original(path)
        if not stat.S_ISDIR(metadata.st_mode): return metadata
        count = observations.get(path, 0)
        observations[path] = count + 1
        attributes = first_attributes ^ (0x10000000 if count % 2 else 0)
        return _observed_directory(metadata, st_file_attributes=attributes)

    def pin(path):
        handle = len(opened)
        opened.append((handle, path))
        return handle, closed.append

    # Exercise both complete captures and the final inventory revalidation on
    # a real tree. Only Windows observation/pinning is simulated on Linux.
    monkeypatch.setattr(tree, 'is_windows', lambda: True)
    monkeypatch.setattr(tree, 'pin_windows_directory', pin)
    monkeypatch.setattr(Path, 'lstat', observe)
    captured = capture_sources(contents, 'run.sh')
    captured.revalidate()
    assert {p.relative_path: p.content for p in captured.files} == {
        'run.sh': SCRIPT, 'nested/data.bin': b'\x00\xffunchanged'}
    assert captured.empty_directories == 1
    assert all(observations[path] > 3 for path in (contents, nested, nested / 'empty'))
    assert sorted(closed) == [handle for handle, _ in opened]


@pytest.mark.parametrize('bit', [1 << n for n in range(32) if n != 28])
def test_windows_directory_attribute_normalization_preserves_every_other_bit(contents, monkeypatch, bit):
    monkeypatch.setattr(tree, 'is_windows', lambda: True)
    before = _observed_directory(contents.lstat(), st_file_attributes=0x10000010)
    after = _observed_directory(before, st_file_attributes=0x10 ^ bit)
    with pytest.raises(tree.FileChangedDuringRead) as caught:
        tree._require_same_directory_metadata(before, after, 'probe')
    delta = json.loads(str(caught.value).split(': ', 1)[1])
    assert delta['st_file_attributes'] == {'before': before.st_file_attributes, 'after': after.st_file_attributes}


@pytest.mark.parametrize('windows,mode,attributes', [
    (False, stat.S_IFDIR | 0o700, 0x10),
    (True, stat.S_IFREG | 0o600, 0x20),
    (True, stat.S_IFREG | 0o600, 0x10),
    (True, stat.S_IFDIR | 0o700, 0),
    (True, stat.S_IFDIR | 0o700, 0x410),
])
def test_ntfs_directory_exception_does_not_extend_to_other_file_kinds(contents, monkeypatch, windows, mode, attributes):
    monkeypatch.setattr(tree, 'is_windows', lambda: windows)
    before = _observed_directory(contents.lstat(), st_mode=mode, st_file_attributes=attributes)
    after = _observed_directory(before, st_file_attributes=attributes | 0x10000000)
    with pytest.raises(tree.FileChangedDuringRead):
        tree._require_same_directory_metadata(before, after, 'probe')


@pytest.mark.parametrize('field', ['st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'])
def test_windows_directory_bit_cannot_hide_a_real_change_or_leak_handle(contents, monkeypatch, field):
    child = contents / 'child'; child.mkdir()
    before = _observed_directory(child.lstat(), st_file_attributes=0x10000010)
    after = _observed_directory(before, st_file_attributes=0x10,
                                **{field: getattr(before, field) + (0o200 if field == 'st_mode' else 1)})
    parent = tree.SourceDirectory(contents, contents.lstat(), None)
    closed = []
    monkeypatch.setattr(tree, 'is_windows', lambda: True)
    monkeypatch.setattr(tree.SourceDirectory, 'child_stat', lambda *a: before)
    monkeypatch.setattr(tree, 'pin_windows_directory', lambda path: (17, closed.append))
    monkeypatch.setattr(Path, 'lstat', lambda path: after)
    with pytest.raises(tree.FileChangedDuringRead) as caught:
        with parent.child('child', before): pytest.fail('changed directory admitted')
    assert closed == [17]
    delta = json.loads(str(caught.value).split(': ', 1)[1])
    assert delta[field] == {'before': getattr(before, field), 'after': getattr(after, field)}


def test_windows_directory_bit_does_not_admit_reparse_point(contents, monkeypatch):
    child = contents / 'child'; child.mkdir()
    before = _observed_directory(child.lstat(), st_file_attributes=0x10000010)
    after = _observed_directory(before, st_file_attributes=0x10000410)
    parent = tree.SourceDirectory(contents, contents.lstat(), None)
    closed = []
    monkeypatch.setattr(tree, 'is_windows', lambda: True)
    monkeypatch.setattr(tree.SourceDirectory, 'child_stat', lambda *a: before)
    monkeypatch.setattr(tree, 'pin_windows_directory', lambda path: (17, closed.append))
    monkeypatch.setattr(Path, 'lstat', lambda path: after)
    with pytest.raises(tree.UnsupportedFileTypeError):
        with parent.child('child', before): pytest.fail('reparse point admitted')
    assert closed == [17]
