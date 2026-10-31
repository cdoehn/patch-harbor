"""Executable-byte generation and PEP 517 gates, independent of document prose."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from scripts import render_chat_bootstrap as generator
from tests.embedded_pyz_support import bootstrap_program
from tests.platform_support import PROJECT_ROOT

SOURCE = b'raise AssertionError("build checks must not execute the bootstrap")\n'
PREFIX = b"independently maintained prefix\n"
SUFFIX = b"\nindependently maintained suffix\n"
TEMPLATE = PREFIX + generator.BEGIN + b"obsolete executable bytes\n" + generator.END + SUFFIX


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "source"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/pyz_bootstrap.py").write_bytes(SOURCE)
    shutil.copyfile(PROJECT_ROOT / "scripts/render_chat_bootstrap.py",
                    root / "scripts/render_chat_bootstrap.py")
    (root / "CHAT_INSTRUCTIONS.md").write_bytes(generator.render(TEMPLATE, SOURCE))
    return root


def snapshot(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r", b""])
def test_generation_is_deterministic_and_only_replaces_executable_bytes(ending):
    source = SOURCE.rstrip(b"\n") + ending
    generated = generator.render(TEMPLATE, source)
    assert bootstrap_program(generated).encode() + b"\n" == SOURCE
    assert generated.partition(generator.BEGIN)[0] == PREFIX
    assert generated.partition(generator.END)[2] == SUFFIX
    assert generator.render(generated, source) == generated


@pytest.mark.parametrize("fault", ["missing_begin", "missing_end", "duplicate_begin",
                                    "duplicate_end", "unmarked_code", "reversed", "syntax", "encoding", "empty", "fence"])
def test_invalid_region_or_source_cannot_be_written(workspace, fault):
    target = workspace / "CHAT_INSTRUCTIONS.md"
    if fault == "missing_begin":
        target.write_bytes(target.read_bytes().replace(generator.BEGIN, b""))
    elif fault == "missing_end":
        target.write_bytes(target.read_bytes().replace(generator.END, b""))
    elif fault == "duplicate_begin":
        target.write_bytes(generator.BEGIN + target.read_bytes())
    elif fault == "duplicate_end":
        target.write_bytes(target.read_bytes() + generator.END)
    elif fault == "unmarked_code":
        target.write_bytes(target.read_bytes() + generator.CODE_PREFIX + SOURCE + b"```\n")
    elif fault == "reversed":
        target.write_bytes(generator.END + generator.BEGIN)
    else:
        invalid = {"syntax": b"def broken(\n", "encoding": b"\xff", "empty": b"\n", "fence": b'"""\n```\n"""\n'}
        (workspace / "scripts/pyz_bootstrap.py").write_bytes(invalid[fault])
    before = snapshot(workspace)
    with pytest.raises((ValueError, SyntaxError)):
        generator.main(["--write", "--root", str(workspace)])
    assert snapshot(workspace) == before


def test_cli_check_is_readonly_and_generation_requires_explicit_write(workspace, tmp_path):
    target = workspace / "CHAT_INSTRUCTIONS.md"
    target.write_bytes(TEMPLATE)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "patchharbor.py").write_text('raise AssertionError("foreign Core imported")\n')
    (outside / "render_chat_bootstrap.py").write_text('raise AssertionError("foreign checker imported")\n')
    prefix = [sys.executable, "-I", "-S", "-B", str(workspace / "scripts/render_chat_bootstrap.py"),
              "--root", str(workspace)]
    before = snapshot(workspace)
    checked = subprocess.run([*prefix, "--check"], cwd=outside, capture_output=True, timeout=30)
    assert checked.returncode == 1 and snapshot(workspace) == before
    written = subprocess.run([*prefix, "--write"], cwd=outside, capture_output=True, timeout=30)
    assert written.returncode == 0, written.stderr
    assert target.read_bytes() == generator.render(TEMPLATE, SOURCE)
    after = snapshot(workspace)
    for action in ("--check", "--write"):
        repeated = subprocess.run([*prefix, action], cwd=outside, capture_output=True, timeout=30)
        assert repeated.returncode == 0 and snapshot(workspace) == after


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


@pytest.mark.parametrize("hook", ["build_wheel", "build_sdist", "build_editable"])
@pytest.mark.parametrize("fault", ["stale", "missing_source", "missing_checker", "ambiguous", "syntax"])
def test_build_rejects_invalid_bootstrap_before_creating_artifacts(workspace, tmp_path, hook, fault):
    if fault == "stale":
        (workspace / "scripts/pyz_bootstrap.py").write_bytes(SOURCE + b"# modified source\n")
    elif fault == "missing_source":
        (workspace / "scripts/pyz_bootstrap.py").unlink()
    elif fault == "missing_checker":
        (workspace / "scripts/render_chat_bootstrap.py").unlink()
    elif fault == "ambiguous":
        target = workspace / "CHAT_INSTRUCTIONS.md"
        target.write_bytes(target.read_bytes() + generator.END)
    else:
        (workspace / "scripts/pyz_bootstrap.py").write_bytes(b"def broken(\n")
    output = tmp_path / "not-created"
    before = snapshot(workspace)
    invoke_build(workspace, hook, [str(output)], reject=True)
    assert snapshot(workspace) == before and not output.exists()


@pytest.mark.parametrize("hook", ["build_sdist", "build_editable"])
def test_checked_build_preserves_frontend_arguments_without_importing_bootstrap(workspace, hook):
    args = ["output", {"key": "value"}] + (["metadata"] if hook == "build_editable" else [])
    before = snapshot(workspace)
    invoke_build(workspace, hook, args, reject=False)
    assert snapshot(workspace) == before


def test_current_executable_handoff_is_generated_from_its_only_source():
    template = (PROJECT_ROOT / "CHAT_INSTRUCTIONS.md").read_bytes()
    source = (PROJECT_ROOT / "scripts/pyz_bootstrap.py").read_text(encoding="utf-8").encode()
    assert generator.render(template, source) == template
    assert bootstrap_program(template).encode() + b"\n" == source
