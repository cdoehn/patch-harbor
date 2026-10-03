"""PEP 517 backend: setuptools transport plus prepared canonical runtime data.

Resources are generated in the wheel, never in the source checkout. Editable
builds retain setuptools semantics and intentionally have no portable runtime.
"""
from __future__ import annotations

import base64
import csv
from email.parser import BytesParser
from email.policy import default as email_policy
import hashlib
import importlib.util
import io
from pathlib import Path
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


def _record(payloads: dict[str, bytes], path: str) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for name, raw in sorted(payloads.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(raw)))
    writer.writerow((path, "", ""))
    return stream.getvalue().encode("utf-8")


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    output = Path(wheel_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patchharbor-build-") as temporary:
        filename = _backend.build_wheel(temporary, config_settings, metadata_directory)
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
        # Rebuild from the current transport every time, never stale source data.
        canonical = {name: raw for name, raw in transport.items()
                     if name.startswith(("patchharbor/", "patchharbor_watcher/"))
                     and not name.startswith(recipe_module.RESOURCE_ROOT)}
        canonical[recipe_module.CHAT_PATH] = (_ROOT / "CHAT_INSTRUCTIONS.md").read_bytes()
        canonical[recipe_module.DOC_PATH] = (_ROOT / "docs/python-api.md").read_bytes()
        for name, raw in transport.items():
            if name.startswith(dist_info + "/") and not name.endswith("/RECORD"):
                suffix = name[len(dist_info) + 1:]
                if suffix == "WHEEL":
                    raw = recipe_module.WHEEL_METADATA
                canonical[name] = raw
                canonical[recipe_module.RESOURCE_ROOT + "metadata/" + suffix] = raw
        recipe = recipe_module.prepare_recipe(canonical, version=version, requires_python=requires)
        # A successful build must already materialize the identical candidate
        # later reconstructed from an ordinary installed transport wheel.
        recipe_module.materialize(recipe, lambda name, size: canonical[name])
        for name in tuple(transport):
            if name.startswith(recipe_module.RESOURCE_ROOT):
                del transport[name]
        transport.update({name: raw for name, raw in canonical.items()
                          if name.startswith(recipe_module.RESOURCE_ROOT)})
        transport[recipe_module.RECIPE_PATH] = recipe.data
        record_path = dist_info + "/RECORD"
        del transport[record_path]
        transport[record_path] = _record(transport, record_path)
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
