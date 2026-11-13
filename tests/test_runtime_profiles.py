"""Runtime profile independence and original-byte compatibility across the split."""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
import shutil
import subprocess
import sys

import pytest

from tests.platform_support import PROJECT_ROOT
from tests.runtime_pyz_support import inputs


def test_current_pyz_paths_do_not_import_legacy_readers(tmp_path):
    program = '''
import importlib.abc, importlib, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
class NoLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'patchharbor.runtime_wheel', 'patchharbor.result_runtime'}:
            raise AssertionError('legacy reader imported: ' + fullname)
sys.meta_path.insert(0, NoLegacy())
for name in ('runtime_pyz', 'result_pyz', 'runtime_sources', 'pyz_artifact', 'result_resources'):
    module = importlib.import_module('patchharbor.' + name)
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[1]))
assert 'patchharbor_watcher' not in sys.modules
'''
    child = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program,
                            str(PROJECT_ROOT / 'src')], cwd=tmp_path, capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
    assert not list(tmp_path.iterdir())




@pytest.mark.parametrize('missing', [None, 'runtime_profile.py', 'runtime_pyz.py',
                                     'runtime_zip.py'])
def test_current_build_uses_only_anchored_data_helpers(tmp_path, missing):
    # Deliberately omit both legacy readers and the package initializer. The
    # current builder must work with just its own finite data helpers, and must
    # fail closed if one of those is missing instead of using an installed copy.
    root = tmp_path / 'anchored'
    package = root / 'src' / 'patchharbor'
    package.mkdir(parents=True)
    for name in ('runtime_profile.py', 'runtime_pyz.py', 'runtime_zip.py'):
        if name != missing:
            shutil.copyfile(PROJECT_ROOT / 'src/patchharbor' / name, package / name)
    payload = inputs()
    (root / 'input.json').write_text(json.dumps({name: raw.hex() for name, raw in payload.items()}))
    foreign = tmp_path / 'foreign'
    (foreign / 'patchharbor').mkdir(parents=True)
    (foreign / 'patchharbor/__init__.py').write_text("raise AssertionError('foreign package executed')\n")
    for name in ('runtime_profile.py', 'runtime_pyz.py', 'runtime_zip.py'):
        (foreign / 'patchharbor' / name).write_text("raise AssertionError('foreign helper executed')\n")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    program = '''
import importlib.abc, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import build_backend
build_backend._ROOT = Path(sys.argv[2])
sys.path.insert(0, sys.argv[3])
class NoInstalledOrLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname == 'patchharbor' or fullname.startswith('patchharbor.')
                or fullname.rsplit('.', 1)[-1] in {'runtime_wheel', 'result_runtime'}):
            raise AssertionError('foreign or legacy helper selected: ' + fullname)
sys.meta_path.insert(0, NoInstalledOrLegacy())
payload = {name:bytes.fromhex(raw) for name,raw in json.loads(
    (build_backend._ROOT / 'input.json').read_bytes()).items()}
try:
    built = build_backend._prepare_pyz_transport(payload, version='1.4.0', requires_python='>=3.10',
        chat=b'controlled template\\n', bootstrap=b'# controlled helper\\n', documentation=b'controlled API documentation\\n',
        license=b'controlled license\\n')
except ModuleNotFoundError:
    assert sys.argv[4] != 'present'
else:
    assert sys.argv[4] == 'present'
    record = 'patchharbor-1.4.0.dist-info/RECORD'
    assert record in built and 'patchharbor/_runtime/pyz-recipe.json' in built
    print(json.dumps({name:raw.hex() for name,raw in built.items()}))
assert 'patchharbor' not in sys.modules
assert not any(name.startswith('_patchharbor_build_profiles_') for name in sys.modules)
'''
    child = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(PROJECT_ROOT),
                            str(root), str(foreign), missing or 'present'], cwd=foreign,
                           capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    if missing is None:
        built = {name: bytes.fromhex(raw) for name, raw in json.loads(child.stdout).items()}
        record_path = 'patchharbor-1.4.0.dist-info/RECORD'
        rows = list(csv.reader(StringIO(built[record_path].decode())))
        assert rows[-1] == [record_path, '', '']
        assert {row[0] for row in rows} == set(built)
        import base64
        for name, encoded, size in rows[:-1]:
            assert encoded == 'sha256=' + base64.urlsafe_b64encode(sha256(built[name]).digest()).rstrip(b'=').decode()
            assert int(size) == len(built[name])
