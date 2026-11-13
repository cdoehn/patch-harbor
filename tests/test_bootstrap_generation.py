"""Standalone resources and PEP 517 gates never execute helper code."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest
from scripts import render_chat_bootstrap as generator
from tests.platform_support import PROJECT_ROOT

SOURCE = (generator.CAP_BEGIN + b"OPERATIONS = ('inspect_task', 'validate_task', 'pack_task')\n"
          b"TASK_FORMATS = (2,)\nRESULT_FORMATS = (4,)\n" + generator.CAP_END +
          b'\nraise AssertionError("build must not execute helper")\n')
TEMPLATE = b"Read tools/pyz_bootstrap.py from this handoff.\n"


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "source"
    for name in ('scripts', 'tools', 'src/patchharbor'):
        (root / name).mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / 'src/patchharbor/runtime_contract.py', root / 'src/patchharbor/runtime_contract.py')
    shutil.copyfile(PROJECT_ROOT / 'scripts/render_chat_bootstrap.py', root / 'scripts/render_chat_bootstrap.py')
    (root / 'tools/pyz_bootstrap.py').write_bytes(SOURCE)
    (root / 'CHAT_INSTRUCTIONS.md').write_bytes(TEMPLATE)
    return root


def snapshot(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('ending', [b'\n', b'\r\n', b'\r'])
def test_capability_generation_is_deterministic_and_readonly(workspace, ending):
    path = workspace / 'tools/pyz_bootstrap.py'
    path.write_bytes(SOURCE.replace(b'\n', ending))
    before = snapshot(workspace)
    generator.check(workspace)
    assert snapshot(workspace) == before
    generator.main(['--write', '--root', str(workspace)])
    assert path.read_bytes() == SOURCE
    assert (workspace / 'CHAT_INSTRUCTIONS.md').read_bytes() == TEMPLATE


def test_cli_refreshes_only_stale_capabilities_without_executing_helper(workspace, tmp_path):
    helper = workspace / 'tools/pyz_bootstrap.py'
    helper.write_bytes(SOURCE.replace(b'TASK_FORMATS = (2,)', b'TASK_FORMATS = (99,)'))
    outside = tmp_path / 'outside'; outside.mkdir()
    (outside / 'patchharbor.py').write_text('raise AssertionError("foreign Core")\n')
    prefix = [sys.executable, '-I', '-S', '-B', str(workspace / 'scripts/render_chat_bootstrap.py'), '--root', str(workspace)]
    before = snapshot(workspace)
    assert subprocess.run([*prefix, '--check'], cwd=outside, capture_output=True, timeout=30).returncode == 1
    assert snapshot(workspace) == before
    written = subprocess.run([*prefix, '--write'], cwd=outside, capture_output=True, timeout=30)
    assert written.returncode == 0, written.stderr
    assert helper.read_bytes() == SOURCE
    assert (workspace / 'CHAT_INSTRUCTIONS.md').read_bytes() == TEMPLATE
    after = snapshot(workspace)
    assert subprocess.run([*prefix, '--check'], cwd=outside, capture_output=True, timeout=30).returncode == 0
    assert snapshot(workspace) == after


def invoke_build(root, hook, args, *, reject):
    # PEP 517 runs backends in their own process. Keep setuptools' initialization
    # (including its vendored import path) outside the pytest worker too.
    program = """
import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
source,root,hook,args,reject=sys.argv[1:]
spec=importlib.util.spec_from_file_location('checked_build_backend',Path(source)/'build_backend.py')
backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
backend._ROOT=Path(root)
def forbidden(*args,**kwargs):raise AssertionError('foreign checker selected')
sys.modules['scripts.render_chat_bootstrap']=SimpleNamespace(check=forbidden)
sys.modules['render_chat_bootstrap']=SimpleNamespace(check=forbidden)
args=json.loads(args);calls=[]
def delegate(*values):
    assert reject=='False','stale source reached the build backend'
    calls.append(list(values))
    return 'artifact'
backend._backend=SimpleNamespace(**{hook:delegate})
try:result=getattr(backend,hook)(*args)
except (ValueError,OSError,SyntaxError):
    assert reject=='True' and not calls
    print(json.dumps({'rejected':True}))
else:
    assert reject=='False' and calls==[args] and result=='artifact'
    print(json.dumps({'rejected':False}))
"""
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", program,
                                str(PROJECT_ROOT), str(root), hook, json.dumps(args), str(reject)],
                               cwd=root, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {"rejected": reject}



@pytest.mark.parametrize('hook', ['build_wheel', 'build_sdist', 'build_editable'])
@pytest.mark.parametrize('fault', ['stale', 'missing_source', 'missing_checker', 'syntax', 'encoding', 'bom', 'oversize', 'missing_link', 'embedded', 'template_bom'])
def test_build_rejects_invalid_resources_before_artifacts(workspace, tmp_path, hook, fault):
    helper = workspace / 'tools/pyz_bootstrap.py'
    template = workspace / 'CHAT_INSTRUCTIONS.md'
    if fault == 'stale': helper.write_bytes(SOURCE.replace(b'TASK_FORMATS = (2,)', b'TASK_FORMATS = (99,)'))
    elif fault == 'missing_source': helper.unlink()
    elif fault == 'missing_checker': (workspace / 'scripts/render_chat_bootstrap.py').unlink()
    elif fault == 'syntax': helper.write_bytes(b'def broken(\n')
    elif fault == 'encoding': helper.write_bytes(b'\xff')
    elif fault == 'bom': helper.write_bytes(b'\xef\xbb\xbf' + SOURCE)
    elif fault == 'oversize': helper.write_bytes(SOURCE + b' ' * (128 * 1024))
    elif fault == 'missing_link': template.write_bytes(b'no helper reference')
    elif fault == 'embedded': template.write_bytes(TEMPLATE + b'# PATCHHARBOR-PYZ-BOOTSTRAP\n')
    elif fault == 'template_bom': template.write_bytes(b'\xef\xbb\xbf' + TEMPLATE)
    before = snapshot(workspace); output = tmp_path / 'not-created'
    invoke_build(workspace, hook, [str(output)], reject=True)
    assert snapshot(workspace) == before and not output.exists()


@pytest.mark.parametrize('hook', ['build_sdist', 'build_editable'])
def test_build_preserves_frontend_arguments(workspace, hook):
    args = ['output', {'key': 'value'}] + (['metadata'] if hook == 'build_editable' else [])
    before = snapshot(workspace)
    invoke_build(workspace, hook, args, reject=False)
    assert snapshot(workspace) == before
