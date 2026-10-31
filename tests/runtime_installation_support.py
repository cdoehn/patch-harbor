"""Shared runtime installation fixtures and behavior probes."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from scripts.build_release import _copy_release_inputs


@pytest.fixture(scope='module')
def installed_producer(tmp_path_factory):
    root=tmp_path_factory.mktemp('pyz-writer-installation')
    source=root/'source';source.mkdir();outside=root/'outside';outside.mkdir()
    _copy_release_inputs(source)
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    environment.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_CONFIG_FILE=os.devnull)
    output=root/'dist'
    _run([sys.executable,'-m','build','--wheel','--no-isolation','--outdir',str(output)],source,environment)
    python=_venv(root/'venv',outside,environment)
    _run([sys.executable,'-m','pip','--python',str(python),'install','--no-index','--no-deps',
          '--no-cache-dir','--no-compile',str(next(output.glob('*.whl')))],outside,environment)
    shutil.rmtree(source);shutil.rmtree(output)
    return python


def _run(command, cwd, environment):
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _venv(root, cwd, environment):
    _run([sys.executable, "-m", "venv", "--without-pip", str(root)], cwd, environment)
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
