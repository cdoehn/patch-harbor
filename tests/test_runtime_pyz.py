"""Closed PYZ data profile, canonical ZIP mutations and finite identities."""
from dataclasses import replace
from io import BytesIO
import json
import struct
from zipfile import ZipFile, ZipInfo, ZIP_STORED, ZIP_DEFLATED

import pytest

from patchharbor import __version__, runtime_pyz as pyz
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY


def inputs():
    payloads = {name: b'# fixture module\n' for name in pyz.REQUIRED - {pyz.IDENTITY_PATH}}
    payloads['patchharbor/py.typed'] = b''
    payloads[pyz.CHAT_PATH] = b'controlled template\n'
    payloads[pyz.DOC_PATH] = b'controlled API documentation\n'
    payloads[pyz.LICENSE_PATH] = b'controlled license\n'
    payloads[pyz.MAIN_PATH] = payloads['__main__.py'] = pyz.MAIN_BYTES
    return payloads


def prepared(payloads=None, *, version=__version__, **kwargs):
    payloads = inputs() if payloads is None else payloads
    recipe, identity = pyz.create_recipe(payloads, version=version, requires_python='>=3.12', **kwargs)
    payloads = {**payloads, pyz.IDENTITY_PATH: identity}
    artifact = pyz.materialize(recipe, lambda name, size: payloads[name])
    return recipe, payloads, artifact


def read(raw, **kwargs):
    return pyz.read_pyz(raw, policy=DEFAULT_RESOURCE_POLICY,
                        remaining_bytes=pyz.MAX_CONTENT_BYTES, **kwargs)


def signed(document):
    document.pop('content_id', None)
    document['content_id'] = pyz.sha256(pyz.recipe_json(document))
    return pyz.recipe_json(document)


def test_pyz_profile_roundtrips_canonically_without_code_execution(monkeypatch):
    payloads = inputs()
    payloads['patchharbor/never_import.py'] = b'raise AssertionError("described code executed")\n'
    recipe, source, artifact = prepared(payloads)
    assert read(artifact) == recipe
    assert pyz.materialize(recipe, lambda name, size: source[name]) == artifact
    assert pyz.parse_recipe(recipe.data) == recipe
    assert recipe.pyz_name == f'patchharbor-{__version__}.pyz'
    with ZipFile(BytesIO(artifact)) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert archive.namelist() == sorted(set(source) | {pyz.RECIPE_PATH})
        assert archive.read('__main__.py') == archive.read(pyz.MAIN_PATH)
        for info in archive.infolist():
            assert info.compress_type == ZIP_STORED
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.create_version == info.extract_version == 20
            assert info.create_system == 3 and info.external_attr == 0o100644 << 16
            assert info.extra == info.comment == b'' and info.flag_bits == 0
        assert not any('watcher/' in name or '.dist-info/' in name for name in archive.namelist())


def test_producer_content_and_artifact_ids_follow_distinct_finite_contracts():
    recipe, source, artifact = prepared(version='1.2.1', source_commit='a'*40)
    document = json.loads(recipe.data)
    entries = [entry for entry in document['entries'] if entry['path'] != pyz.IDENTITY_PATH]
    identity_input = dict(algorithm='patchharbor-pyz-producer-v1', version='1.2.1',
                          requires_python='>=3.12', profile='patchharbor-core-no-watcher-v1',
                          source_commit='a'*40, entries=entries)
    producer = pyz.sha256((json.dumps(identity_input, ensure_ascii=True, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False)+'\n').encode('ascii'))
    assert producer == pyz.producer_id(recipe)
    assert source[pyz.IDENTITY_PATH] == ('# Generated for the PatchHarbor PYZ profile.\nRESOURCE_ID = "'+producer+'"\n').encode()
    unsigned = {key:value for key,value in document.items() if key != 'content_id'}
    assert pyz.sha256(pyz.recipe_json(unsigned)) == recipe.content_id
    assert len({producer, recipe.content_id, pyz.sha256(artifact)}) == 3
    changed = inputs(); changed[pyz.DOC_PATH] += b'new information\n'
    new, _, new_artifact = prepared(changed, version='1.2.1', source_commit='a'*40)
    assert new.content_id != recipe.content_id and pyz.producer_id(new) != producer
    assert pyz.sha256(new_artifact) != pyz.sha256(artifact)


def test_materializer_reads_each_bounded_resource_once_and_rejects_wrong_capture():
    recipe, payloads, _ = prepared()
    calls = []
    def capture(name, size):
        calls.append((name, size)); assert len(payloads[name]) == size; return payloads[name]
    pyz.materialize(recipe, capture)
    assert len({name for name, _ in calls}) == len(calls)
    assert sum(name == pyz.MAIN_PATH for name,_ in calls) == 1
    with pytest.raises(pyz.RuntimeDataError):
        pyz.materialize(recipe, lambda name,size: b'x' * size)
    with pytest.raises(pyz.RuntimeDataError):
        pyz.materialize(replace(recipe, version='2.0.0'), capture)


@pytest.mark.parametrize('name', [
    'patchharbor_watcher/__init__.py', 'foreign/__init__.py', '../outside.py',
    'patchharbor/../outside.py', 'patchharbor/.git/a.py', 'patchharbor/_runtime_identity.py',
    'patchharbor/_runtime/recipe.json', 'patchharbor/_runtime/metadata/METADATA',
    'patchharbor-1.2.1.dist-info/RECORD', 'patchharbor/cache.pyc', 'patchharbor/start.pth',
    'patchharbor/sitecustomize.py', 'patchharbor/usercustomize.py', 'patchharbor/native.so',
    'patchharbor/__pycache__/module.py', 'patchharbor/COM1.py', 'patchharbor/é.py',
    'patchharbor/_runtime/previous.pyz', 'patchharbor/_runtime/previous.whl',
    'patchharbor\\module.py', 'patchharbor/' + 'a'*129 + '.py',
])
def test_hash_consistent_forbidden_inventory_is_rejected(name):
    payloads = inputs(); payloads[name] = b'content'
    with pytest.raises(pyz.RuntimeDataError): prepared(payloads)


@pytest.mark.parametrize('fault', [
    'unknown_field','boolean_version','wrong_profile','wheel_algorithm','commit_short','missing_required',
    'entry_unknown','entry_boolean_size','entry_negative_size','entry_bad_digest','source_alias',
    'order','case_duplicate','case_directory','file_directory','main_mismatch','identity_mismatch',
])
def test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities(fault):
    recipe, payloads, _ = prepared(); doc = json.loads(recipe.data)
    if fault == 'unknown_field': doc['extra'] = None
    elif fault == 'boolean_version': doc['format_version'] = True
    elif fault == 'wrong_profile': doc['profile'] = 'with-watcher'
    elif fault == 'wheel_algorithm': doc['content_id_algorithm'] = 'patchharbor-runtime-content-v1'
    elif fault == 'commit_short': doc['source_commit'] = 'abcdef'
    elif fault == 'missing_required': doc['entries'] = [e for e in doc['entries'] if e['path'] != pyz.LICENSE_PATH]
    elif fault == 'entry_unknown': doc['entries'][0]['extra'] = 1
    elif fault == 'entry_boolean_size': doc['entries'][0]['size'] = True
    elif fault == 'entry_negative_size': doc['entries'][0]['size'] = -1
    elif fault == 'entry_bad_digest': doc['entries'][0]['sha256'] = 'A'*64
    elif fault == 'source_alias': doc['entries'][0]['source'] = 'patchharbor/api.py'
    elif fault == 'order': doc['entries'].reverse()
    elif fault == 'case_duplicate': doc['entries'].append(dict(path='patchharbor/API.py', source='patchharbor/API.py', size=0, sha256=pyz.sha256(b'')))
    elif fault in ('case_directory','file_directory'):
        paths = ('patchharbor/Feature/one.py','patchharbor/feature/two.py') if fault == 'case_directory' else ('patchharbor/a.py','patchharbor/a.py/x.py')
        doc['entries'] += [dict(path=p,source=p,size=0,sha256=pyz.sha256(b'')) for p in paths]
        doc['entries'].sort(key=lambda e:e['path'])
    elif fault == 'main_mismatch': doc['entries'][0]['sha256'] = 'a'*64
    elif fault == 'identity_mismatch':
        payloads[pyz.IDENTITY_PATH] = b'bad identity'
        for entry in doc['entries']:
            if entry['path'] == pyz.IDENTITY_PATH:
                entry.update(size=len(payloads[pyz.IDENTITY_PATH]),sha256=pyz.sha256(payloads[pyz.IDENTITY_PATH]))
    with pytest.raises(pyz.RuntimeDataError):
        changed = pyz.parse_recipe(signed(doc))
        pyz.materialize(changed,lambda name,size:payloads[name])


@pytest.mark.parametrize('kind', ['duplicate_key','nonfinite','whitespace','bom','wrong_content_id'])
def test_noncanonical_recipe_json_is_never_accepted(kind):
    recipe, _, _ = prepared(); raw = recipe.data
    if kind == 'duplicate_key': raw = raw.replace(b'{', b'{"format_version":1,',1)
    elif kind == 'nonfinite': raw = raw.replace(b'"source_commit":null',b'"source_commit":NaN')
    elif kind == 'whitespace': raw += b' '
    elif kind == 'bom': raw = b'\xef\xbb\xbf' + raw
    else:
        doc = json.loads(raw);doc['content_id'] = '0'*64;raw = pyz.recipe_json(doc)
    with pytest.raises(pyz.RuntimeDataError): pyz.parse_recipe(raw)


@pytest.mark.parametrize('fault', ['compressed','mode','timestamp','extra','comment','version','reverse','hidden_entry','duplicate'])
def test_noncanonical_zip_is_rejected_even_when_all_payload_hashes_match(fault):
    _, _, original = prepared()
    with ZipFile(BytesIO(original)) as archive:
        pairs = [(info.filename,archive.read(info)) for info in archive.infolist()]
    if fault == 'reverse': pairs.reverse()
    if fault == 'hidden_entry': pairs.append(('unexpected.py',b'foreign'))
    if fault == 'duplicate': pairs.append(pairs[0])
    stream = BytesIO()
    with ZipFile(stream,'w',compression=ZIP_STORED) as archive:
        for name, raw in pairs:
            info = ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3
            info.external_attr=0o100644<<16;info.create_version=info.extract_version=20
            if fault == 'compressed': info.compress_type=ZIP_DEFLATED
            if fault == 'mode': info.external_attr=0o100755<<16
            if fault == 'timestamp':info.date_time=(2000,1,1,0,0,0)
            if fault == 'extra':info.extra=b'\x55\x54\x00\x00'
            if fault == 'comment':info.comment=b'extra'
            if fault == 'version':info.extract_version=45
            archive.writestr(info,raw)
    with pytest.raises(ValueError): read(stream.getvalue())


@pytest.mark.parametrize('fault', ['prefix','suffix','second_archive','count','local_header','crc'])
def test_raw_zip_boundary_mutations_fail(fault):
    _, _, original=prepared();raw=bytearray(original)
    if fault=='prefix':raw=b'stub'+raw
    elif fault=='suffix':raw+=b'trailer'
    elif fault=='second_archive':raw+=original
    elif fault=='count':struct.pack_into('<HH',raw,len(raw)-14,1,1)
    elif fault=='local_header':raw[4]^=1
    else:raw[14]^=1
    with pytest.raises(ValueError):read(bytes(raw))


def test_false_small_directory_count_is_rejected_before_zipfile_allocation(monkeypatch):
    _, _, original=prepared();raw=bytearray(original)
    struct.pack_into('<HH',raw,len(raw)-14,1,1)
    monkeypatch.setattr(pyz,'ZipFile',lambda *a,**k:pytest.fail('unbounded directory allocation'))
    with pytest.raises(ValueError):read(bytes(raw))


def test_runtime_resource_and_shared_budgets_are_independent(monkeypatch):
    recipe, source, raw = prepared()
    with pytest.raises(ValueError):
        pyz.read_pyz(raw,policy=replace(DEFAULT_RESOURCE_POLICY,max_zip_entries=2),remaining_bytes=pyz.MAX_CONTENT_BYTES)
    with pytest.raises(pyz.RuntimeLimitError):
        pyz.read_pyz(raw,policy=DEFAULT_RESOURCE_POLICY,remaining_bytes=1)
    monkeypatch.setattr(pyz,'MAX_PYZ_BYTES',len(raw)-1)
    with pytest.raises(pyz.RuntimeLimitError):read(raw)
    with pytest.raises(pyz.RuntimeLimitError):pyz.materialize(recipe,lambda name,size:source[name])


@pytest.mark.packaging
def test_normal_wheel_prepares_distinct_finite_profiles_without_watcher_in_pyz(built_result_source):
    from patchharbor import runtime_wheel
    pyz_recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    pyz_raw=pyz.materialize(pyz_recipe,lambda name,size:(built_result_source/name).read_bytes())
    assert read(pyz_raw)==pyz_recipe
    # Production installation retains the Watcher, while only its Core-PYZ
    # runtime profile is prepared. Legacy wheel readers have separate fixtures.
    assert (built_result_source/'patchharbor_watcher/__init__.py').is_file()
    assert not (built_result_source/runtime_wheel.RECIPE_PATH).exists()
    assert not (built_result_source/runtime_wheel.IDENTITY_PATH).exists()
    with ZipFile(BytesIO(pyz_raw)) as archive:
        assert not any(name.startswith('patchharbor_watcher/') for name in archive.namelist())
        assert runtime_wheel.RECIPE_PATH not in archive.namelist()
        assert runtime_wheel.IDENTITY_PATH not in archive.namelist()
        assert 'patchharbor/runtime_wheel.py' in archive.namelist()


@pytest.mark.parametrize('version', [(3, 8), (3, 11)])
def test_generated_entrypoint_rejects_old_python_before_any_core_import(version):
    from io import StringIO
    from types import SimpleNamespace
    stderr = StringIO(); imports = []
    def importer(name, *a, **k):
        imports.append(name)
        if name == 'sys': return SimpleNamespace(version_info=version, stderr=stderr)
        pytest.fail('Core imported before version guard')
    scope = {'__builtins__': {'__import__': importer, 'SystemExit': SystemExit}}
    with pytest.raises(SystemExit) as caught: exec(compile(pyz.MAIN_BYTES, '__main__.py', 'exec'), scope)
    assert caught.value.code == 2 and imports == ['sys'] and stderr.getvalue()


@pytest.mark.packaging
@pytest.mark.parametrize('isolated', [False, True])
def test_built_pyz_entrypoint_imports_shared_cli_without_install_or_watcher(built_result_source, tmp_path, isolated):
    import os
    import subprocess
    import sys
    recipe = pyz.parse_recipe((built_result_source / pyz.RECIPE_PATH).read_bytes())
    raw = pyz.materialize(recipe, lambda name,size:(built_result_source/name).read_bytes())
    candidate = tmp_path / recipe.pyz_name;candidate.write_bytes(raw)
    outside = tmp_path / 'outside';outside.mkdir()
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    flags = ['-I','-S','-B'] if isolated else []
    # Version dispatch imports the same whole CLI/API graph, without an installed
    # distribution lookup. Full PYZ resource operations follow in PP-04B/C.
    child = subprocess.run([sys.executable,*flags,str(candidate),'--version'],cwd=outside,env=env,
                           capture_output=True,text=True,timeout=60)
    assert child.returncode == 0, child.stderr
    assert candidate.read_bytes() == raw and not list(outside.iterdir())
