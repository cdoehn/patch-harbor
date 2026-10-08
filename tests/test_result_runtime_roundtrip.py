"""Real in-place self-update while an installed producer owns an Apply request."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api
from scripts.build_release import _copy_release_inputs
from tests.platform_support import native_python_script, native_value
from tests.registration_support import create_repository, git
from tests.test_runtime_packaging import _run, _venv

pytestmark = pytest.mark.packaging


@pytest.mark.parametrize("exit_code", [0, 23])
def test_installed_self_update_pins_old_runtime_and_template_but_new_repository(tmp_path, exit_code):
    source, outside = tmp_path / "source", tmp_path / "outside"
    source.mkdir(); outside.mkdir()
    _copy_release_inputs(source)
    old_template = (source / "CHAT_INSTRUCTIONS.md").read_text().encode()
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONHOME", "PYTHONPATH")}
    environment.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    wheels = []
    for generation in range(2):
        output = tmp_path / f"dist-{generation}"
        if generation:
            (source / "CHAT_INSTRUCTIONS.md").write_bytes(old_template + b"\nUpdated producer fixture.\n")
        _run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(output)],
             source, environment)
        wheels.append(next(output.glob("*.whl")))
    python = _venv(tmp_path / "installed", outside, environment)
    install = [sys.executable, "-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps",
               "--no-cache-dir", "--no-compile", "--force-reinstall"]
    _run([*install, str(wheels[0])], outside, environment)
    shutil.rmtree(source)
    repository = create_repository(outside / "self-update-repository")
    api.register(repository)
    api.configure_exchange_directory(outside / "exchange", repository=repository)
    context = api.context(repository)
    entrypoint = native_value("run.sh", "run.ps1")
    # Only these isolated installation/repository fixtures are changed. The
    # child entrypoint performs a real offline reinstall and a real Git commit.
    code = (
        "import subprocess,sys; from pathlib import Path; "
        f"subprocess.run({[*install, str(wheels[1])]!r}, check=True); "
        "Path('tracked.txt').write_bytes(b'new committed snapshot\\n'); "
        "subprocess.run(['git','add','tracked.txt'],check=True); "
        "subprocess.run(['git','commit','-m','self update'],check=True); "
        f"sys.exit({exit_code})"
    )
    body = native_python_script(code)
    patch = outside / "self-update.patch.zip"
    with ZipFile(patch, "w") as archive:
        archive.writestr("patch.json", json.dumps({
            "marker": "patch-harbor", "format_version": 1,
            **{key: str(getattr(context, key)) for key in
               ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
            "entrypoint": entrypoint,
        }))
        archive.writestr(entrypoint, body)
    proof = json.loads(_run([str(python), "-I", "-B", "-c", r'''
import hashlib, json, socket, sys
from pathlib import Path
from zipfile import ZipFile
from patchharbor import api
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.result_reader import read_result_reference
def no_network(*args, **kwargs):
    raise AssertionError('Apply producer attempted Python networking')
socket.socket = no_network
before = PyzProvider().capture().artifact
assert before is not None
report = api.apply(Path(sys.argv[1]))
assert report.process_exit_code == int(sys.argv[2])
facts, _ = read_result_reference(report.result_bundle.path)
assert facts.runtime.status == 'embedded' and not facts.warnings
assert facts.runtime.artifact.sha256 == before.pyz_sha256
assert facts.runtime.content_id == before.recipe.content_id
with ZipFile(report.result_bundle.path) as archive:
    assert archive.read(facts.runtime.artifact.path) == before.pyz_bytes
    assert archive.read('CHAT_INSTRUCTIONS.md').endswith(before.chat_template)
    assert archive.read('base/tracked.txt') == b'new committed snapshot\n'
    assert archive.read('logs/execution.log')
    new_context = json.loads(archive.read('context.json'))
assert PyzProvider().capture().reason == 'source_changed'
print(json.dumps({'base_commit': new_context['base_commit'], 'old_content_id': before.recipe.content_id}))
''', str(patch), str(exit_code)], outside, environment))
    assert proof["base_commit"] == git(repository, "rev-parse", "HEAD").stdout.strip()
    assert proof["base_commit"] != str(context.base_commit)
    fresh = _run([str(python), "-I", "-B", "-c",
                  "from patchharbor.pyz_artifact import PyzProvider; "
                  "p=PyzProvider().capture(); assert p.status=='embedded'; print(p.artifact.recipe.content_id)"],
                 outside, environment).strip()
    assert fresh != proof["old_content_id"]
