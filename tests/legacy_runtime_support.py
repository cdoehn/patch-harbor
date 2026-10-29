"""Shared legacy runtime fixtures and behavior probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile
import shutil
import sys

import pytest

from build_backend import _prepare_transport
from patchharbor.runtime_artifact import RuntimeProvider
from patchharbor import __version__, runtime_wheel as runtime
from scripts.build_release import _copy_release_inputs

from tests.platform_support import PROJECT_ROOT


@pytest.fixture(scope="module")
def canonical(prepared):
    return _capture(prepared)


@pytest.fixture(scope="module")
def legacy_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("frozen-result-reader")
    shutil.copytree(PROJECT_ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    fixtures = Path(__file__).parent / "fixtures/result_format1"
    provenance = json.loads((fixtures / "provenance.json").read_bytes())
    # Freeze the inspection consumer with its reader: current inspection may
    # require reference APIs that did not exist in this historical boundary.
    for name, record in provenance["files"].items():
        # Git may use CRLF in a Windows worktree. Restore the historical LF
        # bytes before their digest check and before loading the frozen module.
        raw = (fixtures / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
        (root / record["source_path"]).write_bytes(raw)
    return root / "src", provenance


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("runtime-build")
    source, output = root / "source", root / "dist"
    source.mkdir()
    _copy_release_inputs(source)
    completed = subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist", "--no-isolation",
                                "--outdir", str(output)], cwd=source, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with ZipFile(next(output.glob("*.whl"))) as wheel:
        payloads = {name: wheel.read(name) for name in wheel.namelist()}
    # Explicit legacy data-profile fixture. New normal builds prepare only PYZ;
    # these tests continue checking the old reader/profile without a dual writer.
    metadata = f"patchharbor-{__version__}.dist-info/METADATA"
    assert b"Requires-Python: >=3.10" in payloads[metadata]
    payloads[metadata] = payloads[metadata].replace(b"Requires-Python: >=3.10", b"Requires-Python: >=3.12")
    # The legacy profile admits simple dev extras, not newer conditional build
    # requirements. Keep this synthetic data fixture in that historical profile;
    # the real new distribution and all frozen artifacts remain untouched.
    lines = payloads[metadata].splitlines(keepends=True)
    conditional = [line for line in lines if line.startswith(b"Requires-Dist: tomli")]
    assert len(conditional) == 1 and conditional[0].strip() == (
        b'Requires-Dist: tomli>=2.0.1; python_version < "3.11" and extra == "dev"')
    payloads[metadata] = b"".join(line for line in lines if line not in conditional)
    return _prepare_transport(runtime,payloads,version=__version__,requires_python='>=3.12',
                              chat=payloads[runtime.CHAT_PATH],documentation=payloads[runtime.DOC_PATH])


def _recipe(payloads):
    return runtime.parse_recipe(payloads[runtime.RECIPE_PATH])


def _capture(payloads):
    return runtime.materialize(_recipe(payloads), lambda name, size: payloads[name])


def _rewrite_recipe(document):
    unsigned = {key: value for key, value in document.items() if key != "content_id"}
    encode = lambda doc: (json.dumps(doc, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    document["content_id"] = runtime.sha256(encode(unsigned))
    return encode(document)


def _provider_tree(prepared, root):
    for entry in _recipe(prepared).entries:
        path = root / entry.source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(prepared[entry.source])
    (root / runtime.RECIPE_PATH).write_bytes(prepared[runtime.RECIPE_PATH])
    provider = RuntimeProvider()
    provider._root = root
    provider._producer_id = runtime.producer_id(_recipe(prepared))
    return provider
