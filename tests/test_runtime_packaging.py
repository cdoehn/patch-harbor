"""Installed offline roundtrips, without relying on a retained build wheel."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from scripts.build_release import _copy_release_inputs
from tests.runtime_permissions import readonly_tree
from tests.test_patch_inspection import write_package
from tests.registration_support import create_repository

pytestmark = pytest.mark.packaging


def _run(command, cwd, environment):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _venv(root, cwd, environment):
    _run([sys.executable, "-m", "venv", "--without-pip", str(root)], cwd, environment)
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _install_builder(python, outside, environment):
    site = Path(_run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                     outside, environment).strip())
    distribution = metadata.distribution("setuptools")
    shutil.copytree(distribution.locate_file("setuptools"), site / "setuptools")
    shutil.copytree(distribution.locate_file("_distutils_hack"), site / "_distutils_hack")
    info = next(path for path in distribution.files if str(path).endswith(".dist-info/METADATA"))
    shutil.copytree(distribution.locate_file(info).parent, site / info.parent.name)


@contextmanager
def _readonly_installation(python, outside, environment):
    site = Path(_run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                     outside, environment).strip())
    with readonly_tree(site, owner=outside.parent, environment=environment) as permissions:
        if os.name == "nt":
            assert permissions == {"enforced": True, "method": "windows_dacl"}
        yield


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
        _install_builder(python, outside, environment)
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
        with _readonly_installation(python, outside, environment):
            proof = json.loads(_run([str(python), "-I", "-B", "-c", script, str(destination), str(patch)], outside, environment))
            cli = json.loads(_run([str(python), "-I", "-B", "-c",
                                  "from patchharbor.cli import main; raise SystemExit(main())",
                                  "validate", "--json", str(patch)], outside, environment))
            if generation == 0:
                repository = create_repository(outside / 'foreign-repository')
                produced = json.loads(_run([str(python), '-I', '-B', '-c', '''
import json, socket, sys
from pathlib import Path
from zipfile import ZipFile
from patchharbor import api
from patchharbor.result_reader import read_result_reference
def forbidden(*args, **kwargs):
    raise AssertionError('Result attempted Python networking')
socket.socket = forbidden
repo = Path(sys.argv[1])
api.register(repo)
api.configure_exchange_directory(repo.parent / 'result-exchange', repository=repo)
bundle = api.bundle(repo)
facts, digest = read_result_reference(bundle.path)
assert facts.format_version == 2 and facts.runtime.status == 'embedded'
assert not facts.warnings and facts.context.repository_path == str(repo)
with ZipFile(bundle.path) as archive:
    raw = archive.read(facts.runtime.wheel.path)
    assert len(raw) == facts.runtime.wheel.size
print(json.dumps({'wheel_sha256': facts.runtime.wheel.sha256, 'size': len(raw)}))
''', str(repository)], outside, environment))
                assert produced == {'wheel_sha256': proof['sha256'], 'size': proof['size']}
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


@pytest.mark.parametrize("pin_before_update", [False, True])
def test_same_version_reinstallation_is_bound_to_loaded_producer(tmp_path, pin_before_update):
    source, outside = tmp_path / "source", tmp_path / "outside"
    source.mkdir(); outside.mkdir()
    _copy_release_inputs(source)
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONHOME", "PYTHONPATH")}
    environment.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    wheels = []
    content_ids = []
    for generation in range(2):
        output = tmp_path / f"dist-{generation}"
        if generation:
            template = source / "CHAT_INSTRUCTIONS.md"
            template.write_bytes(template.read_bytes() + b"\nUpdated producer.\n")
        _run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(output)], source, environment)
        wheel = next(output.glob("*.whl"))
        wheels.append(wheel)
        with ZipFile(wheel) as archive:
            content_ids.append(json.loads(archive.read("patchharbor/_runtime/recipe.json"))["content_id"])
    assert wheels[0].name == wheels[1].name and content_ids[0] != content_ids[1]
    python = _venv(tmp_path / "installed", outside, environment)
    install = [sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps",
               "--no-cache-dir", "--no-compile", "--force-reinstall"]
    _run([*install, str(wheels[0])], outside, environment)
    script = '''
import json, sys
import patchharbor
if sys.argv[1] == 'True':
    from patchharbor.runtime_artifact import RuntimeProvider
    provider = RuntimeProvider()
    pinned = provider.capture()
    assert pinned.status == 'embedded'
else:
    assert 'patchharbor.runtime_artifact' not in sys.modules
print('READY', flush=True)
assert sys.stdin.readline() == 'capture\\n'
from patchharbor.runtime_artifact import RuntimeProvider
current = RuntimeProvider().capture()
assert current.status == 'unavailable' and current.reason == 'source_changed', current
if sys.argv[1] == 'True':
    assert provider.capture() is pinned
    assert pinned.artifact.recipe.content_id == sys.argv[2]
print(json.dumps({'reason': current.reason, 'producer_id': patchharbor._runtime_resource_id}))
'''
    process = subprocess.Popen([str(python), "-I", "-B", "-u", "-c", script, str(pin_before_update), content_ids[0]],
                               cwd=outside, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            ready = pool.submit(process.stdout.readline)
            try:
                assert ready.result(timeout=120).strip() == "READY"
            except BaseException:
                process.kill()
                raise
        _run([*install, str(wheels[1])], outside, environment)
        stdout, stderr = process.communicate("capture\n", timeout=300)
        assert process.returncode == 0, stdout + stderr
        assert json.loads(stdout)["reason"] == "source_changed"
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
    fresh = _run([str(python), "-I", "-B", "-c",
                  "from patchharbor.runtime_artifact import RuntimeProvider; "
                  "p = RuntimeProvider().capture(); assert p.status == 'embedded', p; "
                  "print(p.artifact.recipe.content_id)"], outside, environment).strip()
    assert fresh == content_ids[1]


def test_editable_installation_never_claims_prepared_runtime(tmp_path):
    source, outside = tmp_path / "source", tmp_path / "outside"
    source.mkdir(); outside.mkdir()
    _copy_release_inputs(source)
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONHOME", "PYTHONPATH")}
    environment.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    python = _venv(tmp_path / "editable", outside, environment)
    _install_builder(python, outside, environment)
    _run([sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps",
          "--no-cache-dir", "--no-build-isolation", "--editable", str(source)], outside, environment)
    script = ("from patchharbor.runtime_artifact import RuntimeProvider; "
              "p = RuntimeProvider().capture(); assert p.status == 'unavailable' and "
              "p.reason == 'source_not_prepared' and p.artifact is None, p")
    _run([str(python), "-I", "-B", "-c", script], outside, environment)
    code = source / "src/patchharbor/runtime_wheel.py"
    code.write_bytes(code.read_bytes() + b"\n# editable change\n")
    _run([str(python), "-I", "-B", "-c", script], outside, environment)


def test_source_build_ignores_stale_build_outputs_and_preserves_prepared_metadata(tmp_path):
    source, output = tmp_path / "source", tmp_path / "dist"
    source.mkdir(); output.mkdir()
    _copy_release_inputs(source)
    stale = source / "build/lib/patchharbor/api.py"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"raise AssertionError('stale code must never ship')\n")
    os.utime(stale, (2_000_000_000, 2_000_000_000))
    (stale.parent / "extra.py").write_bytes(b"raise AssertionError('stale module')\n")
    generated = source / "src/patchharbor/_runtime_identity.py"
    generated.write_bytes(b"raise AssertionError('stale generated identity')\n")
    resource = source / "src/patchharbor/_runtime/recipe.json"
    resource.parent.mkdir()
    resource.write_bytes(b"stale generated recipe")
    assert not (source / ".git").exists()
    script = '''
from pathlib import Path
import build_backend
metadata = Path('prepared-metadata')
metadata.mkdir()
info = build_backend.prepare_metadata_for_build_wheel(str(metadata))
original = (metadata / info / 'METADATA').read_bytes()
name = build_backend.build_wheel('../dist', metadata_directory=str(metadata / info))
from zipfile import ZipFile
with ZipFile(Path('../dist') / name) as wheel:
    assert wheel.read(info + '/METADATA') == original
'''
    _run([sys.executable, "-B", "-c", script], source, os.environ.copy())
    wheel = next(output.glob("*.whl"))
    first = wheel.read_bytes()
    with ZipFile(wheel) as archive:
        assert archive.read("patchharbor/api.py") == (source / "src/patchharbor/api.py").read_bytes()
        assert "patchharbor/extra.py" not in archive.namelist()
        assert archive.read("patchharbor/_runtime_identity.py") != generated.read_bytes()
    assert resource.read_bytes() == b"stale generated recipe"
    assert stale.read_bytes() == b"raise AssertionError('stale code must never ship')\n"
    outside = tmp_path / "outside"
    foreign = outside / "patchharbor"
    foreign.mkdir(parents=True)
    (foreign / "__init__.py").write_bytes(b"raise AssertionError('foreign CWD package imported')\n")
    (foreign / "runtime_wheel.py").write_bytes(b"raise AssertionError('foreign generator imported')\n")
    script = '''
import os, sys
sys.path.insert(0, sys.argv[1])
import build_backend
os.chdir(sys.argv[2])
sys.path.insert(0, sys.argv[2])
build_backend.build_wheel(sys.argv[3])
assert 'patchharbor' not in sys.modules
'''
    _run([sys.executable, "-I", "-B", "-c", script, str(source), str(outside), str(output)],
         outside, os.environ.copy())
    assert wheel.read_bytes() == first
