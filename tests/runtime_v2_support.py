"""Fresh installed consumers for the version-2 handoff acceptance boundary."""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys

import pytest

from scripts.build_release import _copy_release_inputs
from tests.runtime_installation_support import _run, _venv, installed_producer
from tests.test_runtime_packaging import _install_builder

# Pytest discovers both fixtures when this module is registered as a plugin.
__all__ = ['installed_producer', 'version2_runtime', 'InstalledRuntime', 'offline_environment']


@dataclass(frozen=True)
class InstalledRuntime:
    route: str
    python: Path
    pyz: Path | None = None

    def library(self, source, *arguments):
        prefix = '' if self.pyz is None else f'import sys; sys.path.insert(0, {str(self.pyz)!r});\n'
        return [str(self.python), '-I', '-B', *([] if self.pyz is None else ['-S']),
                '-c', prefix + source, *map(str, arguments)]

    def cli(self, *arguments):
        entry = ['-m', 'patchharbor.cli'] if self.pyz is None else ['-S', str(self.pyz)]
        return [str(self.python), '-I', '-B', *entry, *map(str, arguments)]


@pytest.fixture(scope='module', params=['wheel', 'sdist', 'pyz'])
def version2_runtime(request, tmp_path_factory, installed_producer):
    route = request.param
    if route == 'wheel':
        return InstalledRuntime(route, installed_producer)
    root = tmp_path_factory.mktemp('version2-' + route)
    outside = root / 'outside'
    outside.mkdir()
    environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
    environment.update(PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_CONFIG_FILE=os.devnull)
    if route == 'pyz':
        path = outside / 'runtime.pyz'
        _run([str(installed_producer), '-I', '-B', '-c',
            'import sys; from pathlib import Path; from patchharbor.pyz_artifact import PyzProvider; '
            'artifact=PyzProvider().capture().artifact; assert artifact is not None; '
            'Path(sys.argv[1]).write_bytes(artifact.pyz_bytes)', str(path)], outside, environment)
        return InstalledRuntime(route, Path(sys.executable), path)
    source, output = root / 'source', root / 'dist'
    source.mkdir()
    _copy_release_inputs(source)
    _run([sys.executable, '-m', 'build', '--sdist', '--no-isolation', '--outdir', str(output)], source, environment)
    python = _venv(root / 'installed', outside, environment)
    _install_builder(python, outside, environment)
    _run([sys.executable, '-m', 'pip', '--python', str(python), 'install', '--no-index', '--no-deps',
          '--no-cache-dir', '--no-build-isolation', '--no-compile', str(next(output.glob('*.tar.gz')))], outside, environment)
    shutil.rmtree(source)
    shutil.rmtree(output)
    return InstalledRuntime(route, python)


def offline_environment(user, cache):
    from tests.registration_support import isolated_user_environment
    environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
    environment.update(isolated_user_environment(user))
    environment.update(PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_CONFIG_FILE=os.devnull,
                       XDG_CACHE_HOME=str(cache), PIP_CACHE_DIR=str(cache))
    return environment
