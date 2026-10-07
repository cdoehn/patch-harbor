"""PEP 517 backend: setuptools transport plus prepared canonical runtime data.

Resources are generated in the wheel, never in the source checkout. Editable
builds retain setuptools semantics and intentionally have no portable runtime.
"""
from __future__ import annotations

from email.parser import BytesParser
from email.policy import default as email_policy
import importlib.util
import importlib.machinery
import importlib
from types import ModuleType, SimpleNamespace
from uuid import uuid4
import os
from pathlib import Path
import shutil
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from setuptools import build_meta as _backend


get_requires_for_build_wheel = _backend.get_requires_for_build_wheel
get_requires_for_build_sdist = _backend.get_requires_for_build_sdist
get_requires_for_build_editable = _backend.get_requires_for_build_editable
prepare_metadata_for_build_wheel = _backend.prepare_metadata_for_build_wheel
prepare_metadata_for_build_editable = _backend.prepare_metadata_for_build_editable
build_editable = _backend.build_editable

_ROOT = Path(__file__).resolve().parent


def _recipe_module():
    # Load our anchored, stdlib-only data helper, not an arbitrary CWD package.
    spec = importlib.util.spec_from_file_location(
        "_patchharbor_build_recipe", _ROOT / "src/patchharbor/runtime_wheel.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("missing canonical runtime builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _pyz_recipe_module():
    # A private package namespace permits anchored relative data-helper imports
    # without executing patchharbor.__init__ or selecting an installed package.
    name = '_patchharbor_build_profiles_' + uuid4().hex
    package = ModuleType(name)
    package.__path__ = [str(_ROOT / 'src/patchharbor')]
    package.__package__ = name
    package.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    sys.modules[name] = package
    try:
        return importlib.import_module(name + '.runtime_pyz')
    finally:
        for key in tuple(sys.modules):
            if key == name or key.startswith(name + '.'):
                del sys.modules[key]


def _prepare_pyz_transport(transport: dict[str, bytes], *, version: str,
                           requires_python: str, chat: bytes, documentation: bytes,
                           license: bytes) -> dict[str, bytes]:
    pyz = _pyz_recipe_module()
    canonical = {name: raw for name, raw in transport.items()
                 if name.startswith('patchharbor/') and not name.startswith(pyz.RESOURCE_ROOT)
                 and name not in {pyz.IDENTITY_PATH, 'patchharbor/_runtime_identity.py'}}
    canonical.update({pyz.CHAT_PATH: chat, pyz.DOC_PATH: documentation,
                      pyz.LICENSE_PATH: license, pyz.MAIN_PATH: pyz.MAIN_BYTES,
                      '__main__.py': pyz.MAIN_BYTES})
    recipe, identity = pyz.create_recipe(canonical, version=version, requires_python=requires_python)
    canonical[pyz.IDENTITY_PATH] = identity
    candidate = pyz.materialize(recipe, lambda name, size: canonical[name])
    checked = pyz.read_pyz(candidate,
        policy=SimpleNamespace(max_zip_entries=1000, max_content_bytes=256*1024*1024),
        remaining_bytes=pyz.MAX_CONTENT_BYTES)
    if checked != recipe:
        raise RuntimeError('built PYZ differs from its prepared recipe')
    prepared = dict(transport)
    prepared.update({name: raw for name, raw in canonical.items()
                     if name.startswith(pyz.RESOURCE_ROOT) or name == pyz.IDENTITY_PATH})
    prepared[pyz.RECIPE_PATH] = recipe.data
    runtime = _recipe_module()
    record_path = f'patchharbor-{version}.dist-info/RECORD'
    prepared[record_path] = runtime.wheel_record(
        ((name, runtime.sha256(raw), len(raw)) for name, raw in prepared.items() if name != record_path),
        record_path)
    return prepared


def _prepare_recipe(runtime, payloads: dict[str, bytes], *, version: str, requires_python: str):
    """Build-only recipe construction; validate with the anchored runtime reader."""
    dist_info = f"patchharbor-{version}.dist-info/"
    doc = {
        "marker": "patch-harbor-runtime-recipe", "format_version": 1,
        "distribution": "patchharbor", "version": version, "requires_python": requires_python,
        "content_id_algorithm": runtime.CONTENT_ALGORITHM, "source_commit": None,
        "entries": [{"path": name,
                     "source": runtime.RESOURCE_ROOT + "metadata/" + name[len(dist_info):] if name.startswith(dist_info) else name,
                     "size": len(raw), "sha256": runtime.sha256(raw)} for name, raw in sorted(payloads.items())],
    }
    doc["content_id"] = runtime.sha256(runtime.recipe_json(doc))
    return runtime.parse_recipe(runtime.recipe_json(doc))


def _prepare_transport(runtime, transport: dict[str, bytes], *, version: str,
                       requires_python: str, chat: bytes, documentation: bytes) -> dict[str, bytes]:
    """Prepare one transport inventory without filesystem or request ownership."""
    dist_info = f"patchharbor-{version}.dist-info"
    canonical = {name: raw for name, raw in transport.items()
                 if name.startswith(("patchharbor/", "patchharbor_watcher/"))
                 and not name.startswith(runtime.RESOURCE_ROOT)
                 and name not in {runtime.IDENTITY_PATH, "patchharbor/_pyz_identity.py"}}
    canonical[runtime.CHAT_PATH] = chat
    canonical[runtime.DOC_PATH] = documentation
    for name, raw in transport.items():
        if name.startswith(dist_info + "/") and not name.endswith("/RECORD"):
            suffix = name[len(dist_info) + 1:]
            if suffix == "WHEEL":
                raw = runtime.WHEEL_METADATA
            canonical[name] = raw
            canonical[runtime.RESOURCE_ROOT + "metadata/" + suffix] = raw
    initial = _prepare_recipe(runtime, canonical, version=version, requires_python=requires_python)
    canonical[runtime.IDENTITY_PATH] = runtime.identity_module(runtime.producer_id(initial))
    recipe = _prepare_recipe(runtime, canonical, version=version, requires_python=requires_python)
    # A successful build must already materialize the candidate later read from
    # an ordinary installation, without preserving its downloaded transport.
    runtime.materialize(recipe, lambda name, size: canonical[name])
    record_path = dist_info + "/RECORD"
    prepared = {name: raw for name, raw in transport.items()
                if not name.startswith(runtime.RESOURCE_ROOT)
                and name not in {record_path, "patchharbor/_pyz_identity.py"}}
    prepared.update({name: raw for name, raw in canonical.items()
                     if name.startswith(runtime.RESOURCE_ROOT) or name == runtime.IDENTITY_PATH})
    prepared[runtime.RECIPE_PATH] = recipe.data
    prepared[record_path] = runtime.wheel_record(
        ((name, runtime.sha256(raw), len(raw)) for name, raw in prepared.items()), record_path)
    return prepared


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    output = Path(wheel_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata_directory = str(Path(metadata_directory).resolve()) if metadata_directory else None
    with tempfile.TemporaryDirectory(prefix="patchharbor-build-") as temporary:
        # Setuptools may reuse build/lib based on timestamps. A wheel must derive
        # from current sources even after a same-version rebuild or stale cache.
        source = Path(temporary) / "source"
        source.mkdir()
        for name in ("pyproject.toml", "README.md", "LICENSE", "CHAT_INSTRUCTIONS.md",
                     "MANIFEST.in", "build_backend.py", "setup.cfg"):
            if (_ROOT / name).is_file():
                shutil.copy2(_ROOT / name, source / name)
        for name in ("src", "docs"):
            shutil.copytree(_ROOT / name, source / name, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo", "*.egg-info", "_runtime", "_runtime_identity.py", "_pyz_identity.py"))
        previous_cwd = Path.cwd()
        try:
            os.chdir(source)
            filename = _backend.build_wheel(temporary, config_settings, metadata_directory)
        finally:
            os.chdir(previous_cwd)
        with ZipFile(Path(temporary) / filename) as wheel:
            if len(wheel.namelist()) != len(set(wheel.namelist())):
                raise RuntimeError("duplicate transport wheel paths")
            transport = {info.filename: wheel.read(info) for info in wheel.infolist() if not info.is_dir()}
        metadata_names = [name for name in transport if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError("ambiguous transport metadata")
        metadata_name = metadata_names[0]
        metadata = BytesParser(policy=email_policy).parsebytes(transport[metadata_name])
        version, requires = str(metadata["Version"]), str(metadata["Requires-Python"])
        dist_info = f"patchharbor-{version}.dist-info"
        if metadata_name != dist_info + "/METADATA" or filename != f"patchharbor-{version}-py3-none-any.whl":
            raise RuntimeError("unexpected transport identity")
        recipe_module = _recipe_module()
        transport = _prepare_transport(
            recipe_module, transport, version=version, requires_python=requires,
            chat=(source / "CHAT_INSTRUCTIONS.md").read_bytes(),
            documentation=(source / "docs/python-api.md").read_bytes(),
        )
        transport = _prepare_pyz_transport(
            transport, version=version, requires_python=requires,
            chat=(source / "CHAT_INSTRUCTIONS.md").read_bytes(),
            documentation=(source / "docs/python-api.md").read_bytes(),
            license=(source / "LICENSE").read_bytes(),
        )
        staged = Path(temporary) / (filename + ".prepared")
        with ZipFile(staged, "w", compression=ZIP_DEFLATED) as wheel:
            for name, raw in sorted(transport.items()):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_DEFLATED
                wheel.writestr(info, raw)
        # Frontends own the output directory; only this build's named artifact.
        (output / filename).write_bytes(staged.read_bytes())
    return filename


def build_sdist(sdist_directory, config_settings=None):
    return _backend.build_sdist(sdist_directory, config_settings)
