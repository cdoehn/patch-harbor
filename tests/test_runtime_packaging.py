"""Installed offline roundtrips, without relying on a retained build wheel."""
from __future__ import annotations

from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.build_release import _copy_release_inputs
from tests.test_patch_inspection import write_package

pytestmark = pytest.mark.packaging


def _run(command, cwd, environment):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _venv(root, cwd, environment):
    _run([sys.executable, "-m", "venv", "--without-pip", str(root)], cwd, environment)
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@pytest.mark.parametrize("route", ["wheel", "source", "sdist"])
def test_standard_installation_and_three_offline_canonical_generations(tmp_path, route):
    source, output, outside = tmp_path / "source", tmp_path / "dist", tmp_path / "outside"
    source.mkdir(); outside.mkdir()
    _copy_release_inputs(source)
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONHOME", "PYTHONPATH")}
    environment.update({"PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                        "PIP_CACHE_DIR": str(tmp_path / "installer-cache")})
    _run([sys.executable, "-m", "build", "--wheel", "--sdist", "--no-isolation", "--outdir", str(output)],
         source, environment)
    install_input = {"wheel": next(output.glob("*.whl")), "source": source,
                     "sdist": next(output.glob("*.tar.gz"))}[route]
    python = _venv(tmp_path / "installed-0", outside, environment)
    if route != "wheel":
        # Offline build dependency, prepared locally for the real pip install.
        site = Path(_run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                         outside, environment).strip())
        distribution = metadata.distribution("setuptools")
        shutil.copytree(distribution.locate_file("setuptools"), site / "setuptools")
        shutil.copytree(distribution.locate_file("_distutils_hack"), site / "_distutils_hack")
        info = next(path for path in distribution.files if str(path).endswith(".dist-info/METADATA"))
        shutil.copytree(distribution.locate_file(info).parent, site / info.parent.name)
    _run([sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps",
          "--no-cache-dir", "--no-build-isolation", "--no-compile", str(install_input)], outside, environment)
    shutil.rmtree(source); shutil.rmtree(output)
    shutil.rmtree(tmp_path / "installer-cache", ignore_errors=True)
    cache = tmp_path / "blocked-cache"
    cache.write_bytes(b"not a writable cache directory")
    environment["XDG_CACHE_HOME"] = environment["PIP_CACHE_DIR"] = str(cache)
    fingerprints = []
    previous = None
    patch = outside / "patch.zip"
    write_package(patch)
    for generation in range(3):
        destination = outside / str(generation)
        destination.mkdir()
        script = '''
import hashlib, json, os, socket, subprocess, sys
from pathlib import Path
from patchharbor.runtime_artifact import RuntimeProvider
from patchharbor.chat_instructions import load_chat_template
from patchharbor import api
def forbidden(*args, **kwargs):
    raise AssertionError('provider attempted external work')
socket.socket = subprocess.run = subprocess.Popen = forbidden
os.environ['PATH'] = ''
provider = RuntimeProvider()
provision = provider.capture()
assert provision.status == 'embedded', provision
artifact = provision.artifact
assert artifact is not None and artifact.recipe.source_commit is None
assert provider.capture() is provision
assert artifact.chat_template.decode('utf-8') == load_chat_template()
patch = Path(sys.argv[2])
inspection = api.inspect_patch(patch)
assert inspection.package_sha256 == hashlib.sha256(patch.read_bytes()).hexdigest()
assert api.validate_patch(patch).inspection == inspection
assert not (Path.cwd() / 'SHOULD_NOT_EXIST').exists()
target = Path(sys.argv[1]) / artifact.recipe.wheel_name
target.write_bytes(artifact.wheel_bytes)
print(json.dumps({'sha256': artifact.wheel_sha256, 'size': len(artifact.wheel_bytes),
                  'content_id': artifact.recipe.content_id, 'requires_python': artifact.recipe.requires_python}))
'''
        proof = json.loads(_run([str(python), "-I", "-B", "-c", script, str(destination), str(patch)], outside, environment))
        cli = json.loads(_run([str(python), "-I", "-B", "-c",
                              "from patchharbor.cli import main; raise SystemExit(main())",
                              "validate", "--json", str(patch)], outside, environment))
        assert cli["result"]["scope"] == "package"
        assert not (outside / "SHOULD_NOT_EXIST").exists()
        assert proof["requires_python"] == ">=3.12"
        fingerprints.append(proof)
        current = next(destination.glob("*.whl"))
        if previous is not None:
            assert current.read_bytes() == previous
        previous = current.read_bytes()
        if generation < 2:
            python = _venv(tmp_path / f"installed-{generation + 1}", outside, environment)
            _run([sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps",
                  "--no-cache-dir", "--no-compile", str(current)], outside, environment)
        current.unlink()
    assert fingerprints[0] == fingerprints[1] == fingerprints[2]
