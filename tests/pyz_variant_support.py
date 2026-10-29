"""Closed and deliberately forged PYZ data; never execute described fixtures."""
from io import BytesIO
import json
from zipfile import ZipFile, ZipInfo

from patchharbor import runtime_pyz as pyz
from tests.result_pyz_support import attach_pyz
from tests.result_runtime_support import descriptor, edit_metadata
from tests.reference_support import edit_document
from tests.runtime_pyz_support import inputs
from tests.reference_support import reference_entries, write_reference


def variant(requirement):
    payloads = inputs()
    payloads['__main__.py'] = payloads[pyz.MAIN_PATH] = pyz.main_bytes(requirement)
    payloads['patchharbor/api.py'] = b'raise AssertionError("data reader executed described API")\n'
    recipe, identity = pyz.create_recipe(payloads, version='1.3.0', requires_python=requirement)
    payloads[pyz.IDENTITY_PATH] = identity
    return pyz.materialize(recipe, lambda name, size: payloads[name])


def rewrite(raw, *, payload_changes=None, recipe_changes=None, identity_bytes=None):
    """Rehash even invalid combinations independently of production validators."""
    with ZipFile(BytesIO(raw)) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}
    recipe = json.loads(payloads.pop(pyz.RECIPE_PATH))
    payloads.pop(pyz.IDENTITY_PATH)
    payloads.update(payload_changes or {})
    recipe.update(recipe_changes or {})
    entries = [dict(path=name, source=pyz.MAIN_PATH if name == '__main__.py' else name,
                    size=len(data), sha256=pyz.sha256(data)) for name, data in sorted(payloads.items())]
    producer = dict(algorithm=pyz.PRODUCER_ALGORITHM, version=recipe['version'],
                    requires_python=recipe['requires_python'], profile=recipe['profile'],
                    source_commit=recipe['source_commit'], entries=entries)
    identity = (pyz.identity_module(pyz.sha256(pyz.recipe_json(producer)))
                if identity_bytes is None else identity_bytes)
    payloads[pyz.IDENTITY_PATH] = identity
    entries.append(dict(path=pyz.IDENTITY_PATH, source=pyz.IDENTITY_PATH,
                        size=len(identity), sha256=pyz.sha256(identity)))
    recipe['entries'] = sorted(entries, key=lambda e: e['path'])
    recipe.pop('content_id')
    recipe['content_id'] = pyz.sha256(pyz.recipe_json(recipe))
    payloads[pyz.RECIPE_PATH] = pyz.recipe_json(recipe)
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        for name, data in sorted(payloads.items()):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = info.extract_version = 20
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return stream.getvalue()


def attach_unchecked(files, raw):
    # Start with a valid metadata skeleton, then bind exactly the deliberately
    # forged bytes. Do not let a production parser reject the test setup first.
    files = attach_pyz(files, variant('>=3.12'))
    with ZipFile(BytesIO(raw)) as archive:
        recipe = json.loads(archive.read(pyz.RECIPE_PATH))
    name = 'runtime/patchharbor-' + recipe['version'] + '.pyz'
    for key in list(files):
        if key.startswith('runtime/') and key != 'runtime/runtime.json':
            del files[key]
    files[name] = raw
    artifact = dict(type='pyz', **descriptor(name, raw))
    def update(doc):
        for field in ('version', 'requires_python', 'profile', 'content_id', 'content_id_algorithm'):
            doc[field] = recipe[field]
        doc['provenance']['source_commit'] = recipe['source_commit']
        doc['artifact'] = artifact
    edit_metadata(files, update)
    edit_document(files, 'manifest.json', lambda doc: doc['runtime'].update(artifact=artifact))
    return files


def result_file(tmp_path, raw):
    files, binding = reference_entries(handoff=True)
    files = attach_unchecked(files, raw)
    path = tmp_path / 'reference.zip'
    write_reference(path, files)
    return path, files, binding
