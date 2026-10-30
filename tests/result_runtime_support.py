"""Synthetic Result-3 runtime metadata, including independently forged descriptors."""
from io import BytesIO
import hashlib
import json
from zipfile import ZipFile
from patchharbor import __version__, runtime_pyz as pyz


def descriptor(path, content):
    return {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def edit_document(files, name, mutate):
    document = json.loads(files[name]); mutate(document)
    files[name] = json.dumps(document).encode()


def edit_metadata(files, mutate):
    edit_document(files, "runtime/runtime.json", mutate)
    edit_document(files, "manifest.json", lambda manifest: manifest["runtime"].update(
        metadata=descriptor("runtime/runtime.json", files["runtime/runtime.json"])))


def attach_pyz(files, raw, *, reason='source_not_prepared'):
    files = {name:data for name,data in files.items() if not name.startswith('runtime/')}
    manifest = json.loads(files['manifest.json']); manifest['format_version'] = 3
    doc = dict(marker='patch-harbor-runtime', format_version=2, status='unavailable', reason=reason,
               distribution='patchharbor', version=__version__, requires_python='>=3.12',
               profile=None, content_id=None, content_id_algorithm=None, artifact=None,
               runtime_dependencies=None, provenance=None, capabilities=None)
    if raw is not None:
        with ZipFile(BytesIO(raw)) as archive: recipe = pyz.parse_recipe(archive.read(pyz.RECIPE_PATH))
        path = 'runtime/'+recipe.pyz_name; files[path] = raw
        artifact = dict(type='pyz', **descriptor(path,raw))
        doc.update(status='embedded', reason=None, version=recipe.version, requires_python=recipe.requires_python,
                   profile=pyz.PROFILE, content_id=recipe.content_id, content_id_algorithm=pyz.CONTENT_ALGORITHM,
                   artifact=artifact, runtime_dependencies=[],
                   provenance=dict(mode='canonical_resources',source_commit=recipe.source_commit,recipe_format_version=1),
                   capabilities=dict(operations=['inspect_patch','validate_patch','pack_patch'],
                                     patch_formats=[1], result_formats=[1,2,3]))
    metadata_path = 'runtime/runtime.json';files[metadata_path] = json.dumps(doc).encode()
    manifest['runtime'] = dict(status=doc['status'],reason=doc['reason'],
                              metadata=descriptor(metadata_path,files[metadata_path]),artifact=doc['artifact'])
    files['manifest.json'] = json.dumps(manifest).encode()
    edit_document(files,'logs/run.json',lambda run:run.update(warnings=[] if raw is not None else ['runtime unavailable']))
    return files


def replace_pyz(files, raw):
    doc = json.loads(files['runtime/runtime.json'])
    name = doc['artifact']['path']; files[name] = raw
    item = dict(type='pyz', **descriptor(name, raw))
    edit_metadata(files, lambda doc: doc.update(artifact=item))
    edit_document(files, 'manifest.json', lambda doc: doc['runtime'].update(artifact=item))
