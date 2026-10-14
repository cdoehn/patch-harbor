"""Contracts of actual new builds, independent of interpreter simulations."""
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from zipfile import ZipFile

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from patchharbor import runtime_pyz as pyz


@pytest.mark.packaging
@pytest.mark.parametrize('python', ['3.9.23', '3.10.0', '3.11.0', '3.12.0', '3.14.0'])
def test_built_distribution_and_pyz_agree_on_installation_boundary(built_result_source, python):
    metadata = next(built_result_source.glob('patchharbor-*.dist-info/METADATA'))
    message = BytesParser(policy=default).parsebytes(metadata.read_bytes())
    recipe = pyz.parse_recipe((built_result_source / pyz.RECIPE_PATH).read_bytes())
    assert message['Requires-Python'] == recipe.requires_python == '>=3.10'
    assert (python in SpecifierSet(message['Requires-Python'])) == (python != '3.9.23')
    requirements = [Requirement(row) for row in message.get_all('Requires-Dist', [])]
    environment = {'python_version': '.'.join(python.split('.')[:2]), 'python_full_version': python, 'extra': ''}
    assert not [r for r in requirements if r.marker is None or r.marker.evaluate(environment)]
    environment['extra'] = 'dev'
    parsers = [r for r in requirements if r.name == 'tomli' and r.marker.evaluate(environment)]
    assert bool(parsers) == (python.startswith(('3.9.', '3.10.')))
    # Native execution of 3.10/3.11 is a CI gate, not implied by metadata checks.
    raw = pyz.materialize(recipe, lambda name, size: (built_result_source / name).read_bytes())
    with ZipFile(BytesIO(raw)) as archive:
        assert archive.read('__main__.py') == archive.read(pyz.MAIN_PATH) == pyz.MAIN_BYTES_310
        assert not any(name.startswith(('tomli/', 'tomllib/', 'patchharbor_watcher/'))
                       or '.dist-info/' in name for name in archive.namelist())
