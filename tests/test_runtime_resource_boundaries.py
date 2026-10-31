"""Provider attacks retained after removal of the Result-wheel implementation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from patchharbor import pyz_artifact as provider_module, runtime_pyz as pyz
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.runtime_sources import DirectoryResources
from patchharbor.platform.filesystem import FileReadLimitExceeded, read_stable_regular_file_bounded
from patchharbor import runtime_sources
from tests.runtime_pyz_support import provider_for, prepared


def test_installation_directory_named_src_is_supported(tmp_path, monkeypatch):
    provider, source, _, _ = provider_for(monkeypatch, tmp_path)
    target = tmp_path/'src'; source.root.rename(target)
    monkeypatch.setattr(provider_module, 'own_resources', lambda: DirectoryResources(target))
    assert provider.capture().status == 'embedded'


@pytest.mark.parametrize('cache', ['absent', 'corrupt'])
def test_concurrent_requests_need_no_cache_or_temporary_files(tmp_path, monkeypatch, cache):
    provider, _, _, _ = provider_for(monkeypatch,tmp_path)
    path = tmp_path/'cache'
    if cache == 'corrupt': path.write_bytes(b'not a directory')
    monkeypatch.setenv('XDG_CACHE_HOME',str(path));monkeypatch.setenv('TMPDIR',str(path))
    before={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    barrier=Barrier(4)
    def capture(_):barrier.wait(timeout=30);return provider.capture()
    with ThreadPoolExecutor(4) as pool: results=list(pool.map(capture,range(4)))
    assert results[0].status=='embedded' and all(result is results[0] for result in results)
    with ThreadPoolExecutor(4) as pool: separate=list(pool.map(lambda _:PyzProvider().capture(),range(4)))
    assert all(result==results[0] and result is not results[0] for result in separate)
    assert before=={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_parent_directory_replaced_during_resource_read_is_rejected(tmp_path,monkeypatch):
    provider, _, _, _ = provider_for(monkeypatch,tmp_path)
    original=runtime_sources.read_stable_regular_file_bounded
    def replaced(path,**kwargs):
        result=original(path,**kwargs)
        if path.name=='pyz-recipe.json':
            path.parent.rename(path.parent.with_name('saved-runtime'))
            path.parent.mkdir()
        return result
    monkeypatch.setattr(runtime_sources,'read_stable_regular_file_bounded',replaced)
    assert provider.capture().reason=='resources_invalid'


@pytest.mark.parametrize('raw',[b'{"marker":1,"marker":2}',b'{"marker":NaN}',b'['*2000])
def test_invalid_json_never_reaches_payload_reads(tmp_path,monkeypatch,raw):
    provider, source, _, _=provider_for(monkeypatch,tmp_path)
    (source.root/pyz.RECIPE_PATH).write_bytes(raw)
    monkeypatch.setattr(provider_module,'materialize',lambda *a,**k:pytest.fail('invalid recipe read payload'))
    assert provider.capture().reason=='resources_invalid'


def test_unavailable_capture_is_pinned_per_request(tmp_path,monkeypatch):
    provider, source, _, _=provider_for(monkeypatch,tmp_path)
    target=source.root/pyz.CHAT_PATH;original=target.read_bytes();target.unlink()
    result=provider.capture();assert result.reason=='resources_missing'
    target.write_bytes(original)
    assert provider.capture() is result
    assert PyzProvider().capture().status=='embedded'


@pytest.mark.parametrize('field,value',[('version','9.9'),('entries',()),('content_id','0'*64)])
def test_constructed_recipe_cannot_bypass_validated_bytes(field,value):
    recipe, _, _=prepared()
    def forbidden(*args):pytest.fail('forged recipe read a resource')
    with pytest.raises(pyz.RuntimeDataError):pyz.materialize(replace(recipe,**{field:value}),forbidden)


@pytest.mark.parametrize("data,limit", [(b"", 0), (b"abc", 3), (b"abc", 2)])
def test_bounded_native_file_reader(data, limit, tmp_path):
    path = tmp_path / "resource"
    path.write_bytes(data)
    if len(data) > limit:
        with pytest.raises(FileReadLimitExceeded):
            read_stable_regular_file_bounded(path, max_bytes=limit)
    else:
        assert read_stable_regular_file_bounded(path, max_bytes=limit).content == data
