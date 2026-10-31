"""Shared runtime pyz fixtures and behavior probes."""
from __future__ import annotations

from patchharbor import pyz_artifact as provider_module, runtime_pyz as pyz
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.runtime_sources import DirectoryResources, ZipResources
from patchharbor import __version__


def provider_for(monkeypatch, tmp_path, *, kind='directory', payloads=None):
    recipe, payloads, archive = prepared(payloads)
    if kind == 'directory':
        root = tmp_path/'installation'; root.mkdir()
        for name, raw in {**payloads, pyz.RECIPE_PATH: recipe.data}.items():
            if name == '__main__.py': continue
            target = root/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        source = DirectoryResources(root)
    else:
        path = tmp_path/'own.pyz'; path.write_bytes(archive); source = ZipResources(path)
    monkeypatch.setattr(provider_module, 'own_resources', lambda: source)
    monkeypatch.setattr(provider_module, '_pyz_resource_id', pyz.producer_id(recipe))
    return PyzProvider(), source, recipe, archive


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
