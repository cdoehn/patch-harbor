"""Reader-first Python variants, byte-frozen legacy artifacts and import guards."""
from dataclasses import replace
from io import BytesIO, StringIO
import json
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from patchharbor import api, runtime_pyz as pyz
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exit_status import exit_code_for_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import read_result_reference
from scripts import pyz_bootstrap as bootstrap
from tests.pyz_variant_support import variant, rewrite, attach_unchecked
from tests.result_pyz_support import attach_pyz
from tests.result_runtime_support import edit_metadata
from tests.test_reference_validation import reference_entries, write_reference, bound_package, edit_document

FIXTURES = Path(__file__).parent / 'fixtures/python_variants'


def read(raw):
    return pyz.read_pyz(raw, policy=DEFAULT_RESOURCE_POLICY, remaining_bytes=pyz.MAX_CONTENT_BYTES)


def result_file(tmp_path, raw):
    files, binding = reference_entries(handoff=True)
    files = attach_unchecked(files, raw)
    path = tmp_path / 'reference.zip'
    write_reference(path, files)
    return path, files, binding


@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
def test_both_closed_variants_pass_static_reference_and_bootstrap_without_import(tmp_path, monkeypatch, requirement):
    raw = variant(requirement)
    recipe = read(raw)
    assert recipe.requires_python == requirement
    path, _, binding = result_file(tmp_path, raw)
    patch = tmp_path / 'patch.zip'; bound_package(patch, binding)
    monkeypatch.setattr(bootstrap.importlib, 'import_module', lambda *a, **k: pytest.fail('data imported'))
    assert api.validate_patch(patch, reference_bundle=path).binding_matches
    assert parse_archive_evidence(path.read_bytes(), path).kind == 'result_bundle'
    assessment = bootstrap.assess(path)
    assert assessment.requires_python == requirement and assessment.pyz_bytes == raw
    assert not assessment.full_reference_valid and not assessment.source_trusted
    assert bootstrap._main_bytes(requirement) == pyz.main_bytes(requirement)


@pytest.mark.parametrize('requirement', ['>=3.9', '>=3.11', '>=3.100', '>=3.10,<4', ' >=3.10',
                                         '3.10', None, True, 3.10, [], {}])
def test_unknown_python_contract_is_rejected_even_with_recomputed_ids(tmp_path, requirement):
    raw = rewrite(variant('>=3.10'), recipe_changes={'requires_python': requirement})
    with pytest.raises(pyz.RuntimeDataError): read(raw)
    path, _, binding = result_file(tmp_path, raw)
    patch = tmp_path / 'patch.zip'; bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError) as caught: api.validate_patch(patch, reference_bundle=path)
    assert int(exit_code_for_error(caught.value)) == 4
    with pytest.raises(ValueError): bootstrap.assess(path)


@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
@pytest.mark.parametrize('fault', ['both_other_start', 'one_other_start', 'custom_start', 'extra_recipe',
                                  'recipe_profile', 'identity', 'metadata_requirement', 'metadata_version',
                                  'metadata_content', 'metadata_commit'])
def test_rehashed_variant_disagreements_never_become_valid_references(tmp_path, requirement, fault):
    raw = variant(requirement)
    other = '>=3.10' if requirement == '>=3.12' else '>=3.12'
    if fault == 'both_other_start':
        raw = rewrite(raw, payload_changes={n: pyz.main_bytes(other) for n in ('__main__.py', pyz.MAIN_PATH)})
    elif fault == 'one_other_start': raw = rewrite(raw, payload_changes={'__main__.py': pyz.main_bytes(other)})
    elif fault == 'custom_start':
        raw = rewrite(raw, payload_changes={n: b'raise AssertionError("unexpected start")\n'
                                           for n in ('__main__.py', pyz.MAIN_PATH)})
    elif fault == 'extra_recipe': raw = rewrite(raw, recipe_changes={'extra': None})
    elif fault == 'recipe_profile': raw = rewrite(raw, recipe_changes={'profile': 'other'})
    elif fault == 'identity': raw = rewrite(raw, identity_bytes=pyz.identity_module('0' * 64))
    if not fault.startswith('metadata_'):
        with pytest.raises(pyz.RuntimeDataError): read(raw)
    path, files, binding = result_file(tmp_path, raw)
    if fault == 'metadata_requirement': edit_metadata(files, lambda d: d.update(requires_python=other))
    elif fault == 'metadata_version': edit_metadata(files, lambda d: d.update(version='9.9'))
    elif fault == 'metadata_content': edit_metadata(files, lambda d: d.update(content_id='0' * 64))
    elif fault == 'metadata_commit': edit_metadata(files, lambda d: d['provenance'].update(source_commit='a' * 40))
    write_reference(path, files)
    patch = tmp_path / 'patch.zip'; bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError): api.validate_patch(patch, reference_bundle=path)
    with pytest.raises((ValueError, KeyError)): bootstrap.assess(path)


@pytest.mark.parametrize('requirement', [None, '>=3.12', '>=3.10', '>=3.11'])
def test_unavailable_metadata_retains_only_known_closed_requirements(tmp_path, requirement):
    files, _ = reference_entries(handoff=True)
    files = attach_pyz(files, None)
    edit_metadata(files, lambda d: d.update(requires_python=requirement))
    path = tmp_path / 'unavailable.zip'; write_reference(path, files)
    if requirement == '>=3.11':
        with pytest.raises(api.PatchHarborError): read_result_reference(path)
        with pytest.raises(ValueError): bootstrap.assess(path)
    else:
        facts, _ = read_result_reference(path)
        assert facts.runtime.requires_python == requirement and facts.runtime.artifact is None
        with pytest.raises(bootstrap.BootstrapUnavailable): bootstrap.assess(path)


@pytest.mark.parametrize('version', [1, 2, 3])
def test_frozen_reference_formats_remain_byte_exact_and_readable(tmp_path, version):
    provenance = json.loads((FIXTURES / 'provenance.json').read_bytes())
    path = FIXTURES / f'result-format{version}.zip'
    record = provenance['files'][path.name]
    original = path.read_bytes()
    assert len(original) == record['bytes'] and pyz.sha256(original) == record['sha256']
    facts, digest = read_result_reference(path)
    assert facts.format_version == version and digest == record['sha256']
    patch = tmp_path / 'bound.zip'; bound_package(patch, provenance['binding'])
    assert api.validate_patch(patch, reference_bundle=path).binding_matches
    assert path.read_bytes() == original
    if version == 3:
        with ZipFile(path) as archive: raw = archive.read('runtime/patchharbor-1.3.0.pyz')
        recipe = read(raw)
        assert pyz.sha256(raw) == provenance['pyz_sha256'] and len(raw) == provenance['pyz_bytes']
        assert recipe.content_id == provenance['pyz_content_id']
        assert pyz.producer_id(recipe) == provenance['pyz_producer_id']
        with ZipFile(BytesIO(raw)) as archive:
            assert archive.read('__main__.py') == archive.read(pyz.MAIN_PATH) == pyz.MAIN_BYTES
        assert pyz.sha256(pyz.MAIN_BYTES) == provenance['legacy_main_sha256']


@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
@pytest.mark.parametrize('version', [(3, 9), (3, 10), (3, 11), (3, 12), (3, 14)])
def test_bootstrap_separates_static_readability_from_selected_runtime_minimum(tmp_path, monkeypatch, requirement, version):
    path, _, _ = result_file(tmp_path, variant(requirement))
    # Only the bootstrap's interpreter view is simulated; never claim a native
    # old-Python process from this boundary test.
    monkeypatch.setattr(bootstrap, 'sys', SimpleNamespace(version_info=version))
    monkeypatch.setattr(bootstrap, '_legacy_windows', lambda: sys.platform == 'win32' and sys.version_info < (3, 12))
    assessment = bootstrap.assess(path, trusted_source_sha256=pyz.sha256(path.read_bytes()))
    target = tmp_path / 'private'
    if version < bootstrap.PYTHON_MINIMA[requirement]:
        with pytest.raises(bootstrap.BootstrapUnavailable): bootstrap.prepare(assessment, target)
        assert not target.exists()
    else:
        prepared = bootstrap.prepare(assessment, target)
        assert prepared.path.read_bytes() == assessment.pyz_bytes


@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
@pytest.mark.parametrize('version', [(3, 9), (3, 10), (3, 11), (3, 12)])
def test_both_canonical_entrypoints_guard_before_core_import(requirement, version):
    imports = []
    def importer(name, *a, **k):
        imports.append(name)
        if name == 'sys': return SimpleNamespace(version_info=version, stderr=StringIO())
        assert name == 'patchharbor.cli'
        return SimpleNamespace(main=lambda: 17)
    with pytest.raises(SystemExit) as caught:
        exec(compile(pyz.main_bytes(requirement), '__main__.py', 'exec'),
             {'__builtins__': {'__import__': importer, 'SystemExit': SystemExit}})
    allowed = version >= bootstrap.PYTHON_MINIMA[requirement]
    assert caught.value.code == (17 if allowed else 2)
    assert imports == (['sys', 'patchharbor.cli'] if allowed else ['sys'])


def test_relabelled_assessment_cannot_bypass_original_artifact_minimum(tmp_path, monkeypatch):
    path = FIXTURES / 'result-format3.zip'
    assessment = bootstrap.assess(path, trusted_source_sha256=pyz.sha256(path.read_bytes()))
    monkeypatch.setattr(bootstrap, 'sys', SimpleNamespace(version_info=(3, 10)))
    assessment = replace(assessment, requires_python='>=3.10')
    with pytest.raises(ValueError): bootstrap.prepare(assessment, tmp_path / 'unused')
    assert not (tmp_path / 'unused').exists()


@pytest.mark.parametrize('fault', ['count', 'hidden_count', 'total', 'shared_total', 'hash', 'identity', 'extra_member'])
def test_inner_budgets_and_hashes_precede_bootstrap_import(tmp_path, monkeypatch, fault):
    raw = variant('>=3.10')
    if fault == 'hidden_count':
        raw = bytearray(raw); struct.pack_into('<HH', raw, len(raw)-14, 1, 1); raw = bytes(raw)
    if fault == 'hash':
        raw = raw.replace(b'data reader executed described API', b'data reader EXECUTED described API')
    elif fault == 'identity':
        raw = rewrite(raw, identity_bytes=pyz.identity_module('0' * 64))
    elif fault == 'extra_member': raw = rewrite(raw, payload_changes={'patchharbor_watcher/x.py': b'forbidden'})
    if fault == 'count': monkeypatch.setattr(bootstrap, 'MAX_INNER_ENTRIES', 2)
    elif fault == 'total': monkeypatch.setattr(bootstrap, 'MAX_INNER_TOTAL', 1)
    if fault in {'count', 'hidden_count'}:
        monkeypatch.setattr(bootstrap, 'ZipFile', lambda *a, **k: pytest.fail('unbounded inner metadata allocation'))
    from zipfile import BadZipFile
    with pytest.raises((ValueError, BadZipFile)):
        bootstrap._pyz_precheck(raw, dict(requires_python='>=3.10'), 1 if fault == 'shared_total' else pyz.MAX_CONTENT_BYTES)


@pytest.mark.packaging
def test_writer_uses_python310_requirement_and_start_bytes(built_result_source):
    from patchharbor.result_resources import runtime_payload
    recipe = pyz.parse_recipe((built_result_source / pyz.RECIPE_PATH).read_bytes())
    assert recipe.requires_python == '>=3.10'
    assert (built_result_source / pyz.MAIN_PATH).read_bytes() == pyz.MAIN_BYTES_310
    assert json.loads(runtime_payload(None, reason='source_not_prepared').metadata)['requires_python'] == '>=3.10'


@pytest.mark.packaging
@pytest.mark.skipif(sys.version_info < (3, 12), reason='historical 1.3.0 runtime itself requires Python 3.12')
@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
def test_complete_frozen_130_reader_keeps_or_rejects_variant_without_mixed_modules(tmp_path, requirement):
    with ZipFile(FIXTURES / 'result-format3.zip') as archive:
        old = archive.read('runtime/patchharbor-1.3.0.pyz')
    runtime = tmp_path / 'original.pyz'; runtime.write_bytes(old)
    reference, _, binding = result_file(tmp_path, variant(requirement))
    patch = tmp_path / 'patch.zip'; bound_package(patch, binding)
    outcome = subprocess.run([sys.executable, '-I', '-S', '-B', str(runtime), 'validate', str(patch),
                              '--reference-bundle', str(reference), '--json'], cwd=tmp_path,
                             capture_output=True, text=True, timeout=60)
    assert outcome.returncode == (0 if requirement == '>=3.12' else 4), outcome.stderr
    assert json.loads(outcome.stdout)['success'] is (requirement == '>=3.12')
    assert runtime.read_bytes() == old


@pytest.mark.packaging
@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10'])
def test_built_reader_variant_bootstraps_and_packs_in_fresh_stdlib_process(built_result_source, tmp_path, requirement):
    recipe = pyz.parse_recipe((built_result_source / pyz.RECIPE_PATH).read_bytes())
    raw = pyz.materialize(recipe, lambda name, size: (built_result_source / name).read_bytes())
    # Explicit variant fixture; the normal writer now produces >=3.10.
    if requirement == '>=3.12' and sys.version_info < (3, 12):
        pytest.skip('legacy variant execution requires Python 3.12; static reading is tested separately')
    raw = rewrite(raw, recipe_changes={'requires_python': requirement},
                  payload_changes={n: pyz.main_bytes(requirement) for n in ('__main__.py', pyz.MAIN_PATH)})
    reference, _, _ = result_file(tmp_path, raw)
    contents = tmp_path / 'contents'; contents.mkdir(); (contents / 'run.sh').write_bytes(b'# PATCHHARBOR\nexit 0\n')
    output = tmp_path / 'output'; output.mkdir()
    script = '''
import hashlib, importlib.util, json, os, socket, subprocess, sys
from pathlib import Path
helper, reference, workspace, contents, output = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('reviewed_bootstrap', helper)
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
def forbidden(*a, **k): raise AssertionError('external operation')
subprocess.run = subprocess.Popen = socket.socket = forbidden
os.environ['PATH'] = ''
assert not any(n == 'patchharbor' or n.startswith('patchharbor.') for n in sys.modules)
assessment = module.assess(reference, trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
prepared = module.prepare(assessment, workspace)
api = module.import_api(prepared)
packed = api.pack_patch(contents, reference_bundle=reference, entrypoint='run.sh', output_directory=output)
assert api.inspect_patch(packed.path).package_sha256 == packed.package_sha256
assert api.validate_patch(packed.path, reference_bundle=reference).binding_matches
assert not any(n == 'patchharbor_watcher' or n.startswith('patchharbor_watcher.') for n in sys.modules)
print(json.dumps({'requirement': assessment.requires_python, 'path': str(packed.path), 'origin': api.__file__}))
'''
    outcome = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', script, str(Path(bootstrap.__file__).resolve()),
                              str(reference), str(tmp_path / 'runtime'), str(contents), str(output)],
                             cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert outcome.returncode == 0, outcome.stdout + outcome.stderr
    report = json.loads(outcome.stdout)
    assert report['requirement'] == requirement and str(tmp_path / 'runtime') in report['origin']
    assert api.validate_patch(report['path'], reference_bundle=reference).binding_matches
