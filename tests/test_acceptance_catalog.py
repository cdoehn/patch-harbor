"""Acceptance catalogue, generated workflow data and build roles stay aligned."""
from copy import deepcopy
import json
from zipfile import ZipFile

import pytest

from scripts import capture_ci_build, render_acceptance_matrix
from tests.acceptance_support import workflow_matrices
from tools.acceptance_catalog import CATALOG, LANES, artifact_names, required_proofs


def test_catalog_preserves_all_twelve_existing_platform_python_and_shell_lanes():
    actual = {(lane.group, lane.runner, lane.python, lane.windows_engine, lane.ubuntu) for lane in LANES}
    expected = {('acceptance', runner, python, engine, '')
                for runner, engine in (('ubuntu-24.04', ''), ('windows-2025', 'powershell.exe'))
                for python in ('3.10', '3.11', '3.12')}
    expected.add(('acceptance', 'ubuntu-26.04', '3.14', '', ''))
    expected.update(('windows-powershell7-acceptance', 'windows-2025', python, 'pwsh', '')
                    for python in ('3.10', '3.11', '3.12'))
    expected.update(('ubuntu-docker-integration', 'ubuntu-24.04', '3.12', '', ubuntu)
                    for ubuntu in ('24.04', '26.04'))
    assert len(LANES) == len(actual) == 12 and actual == expected
    for lane in LANES:
        assert lane.suites == (('windows',) if lane.windows_engine == 'pwsh' else ('core', 'e2e', 'platform', 'packaging'))
        proofs = required_proofs(lane)
        assert {v for i, v in proofs if i == 'pyz.own-instruction-apply'} == {'full', 'diff', 'mixed'}
        assert {v for i, v in proofs if i == 'installation.three-generations'} == {'wheel', 'source', 'sdist'}
        assert {v for i, v in proofs if i == 'pyz.stdlib-variant'} == {'>=3.10'}
        assert (('installation.uv', 'default') in proofs) == (lane.platform == 'Linux' and lane.python == '3.14')
        assert {v for i, v in proofs if i == 'handoff.commit-sequence'} == (set() if lane.windows_engine == 'pwsh' else {'0', '1', '3'})
        assert {v for i, v in proofs if i == 'windows.private-dacl'} == ({'named', 'random'} if lane.platform == 'Windows' else set())


def test_checked_in_matrix_matches_catalog_and_deterministic_generator():
    original = render_acceptance_matrix.WORKFLOW.read_text(encoding='utf-8')
    matrices = workflow_matrices(original)
    assert set(matrices) == {lane.group for lane in LANES}
    for group, rows in matrices.items():
        assert rows == [lane.matrix() for lane in LANES if lane.group == group]
    assert render_acceptance_matrix.render(original) == original
    assert render_acceptance_matrix.main(['--check']) == 0


def test_matrix_check_detects_drift_without_writing_or_changing_other_steps(tmp_path, monkeypatch):
    original = render_acceptance_matrix.WORKFLOW.read_text(encoding='utf-8')
    modified = original.replace('runner: "ubuntu-24.04"', 'runner: "foreign-runner"', 1)
    modified = modified.replace('timeout-minutes: 120', 'timeout-minutes: 119')
    path = tmp_path / 'workflow.yml'; path.write_text(modified, encoding='utf-8')
    monkeypatch.setattr(render_acceptance_matrix, 'WORKFLOW', path)
    assert render_acceptance_matrix.main(['--check']) == 1 and path.read_text() == modified
    assert render_acceptance_matrix.main([]) == 0
    assert path.read_text() == original.replace('timeout-minutes: 120', 'timeout-minutes: 119')
    assert render_acceptance_matrix.main(['--check']) == 0


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'reversed'])
def test_matrix_generator_rejects_ambiguous_boundaries(fault):
    original = render_acceptance_matrix.WORKFLOW.read_text(encoding='utf-8')
    marker = '      # BEGIN acceptance-catalog: acceptance\n'
    if fault == 'missing': text = original.replace(marker, '')
    elif fault == 'duplicate': text = marker + original
    else:
        end = '      # END acceptance-catalog: acceptance\n'
        text = original.replace(marker, 'SWAP\n').replace(end, marker).replace('SWAP\n', end)
    with pytest.raises(ValueError): render_acceptance_matrix.render(text)


def test_build_capture_emits_versioned_roles_and_requires_current_test_reports(tmp_path, monkeypatch):
    root = tmp_path / 'repo'; root.mkdir()
    monkeypatch.setattr(capture_ci_build, 'ROOT', root)
    binding = {'source_sha256': 'a' * 64, 'python': '3.14.1', 'platform': 'Linux'}
    monkeypatch.setattr(capture_ci_build, 'input_binding', lambda *args: deepcopy(binding))
    monkeypatch.setattr(capture_ci_build.metadata, 'version', lambda name: '1.0')
    def build(directory):
        names = artifact_names('1.4.0')
        wheel = directory / names['wheel']
        with ZipFile(wheel, 'w') as archive:
            archive.writestr('patchharbor/_runtime/pyz-recipe.json', json.dumps({
                'version': '1.4.0', 'requires_python': '>=3.10', 'content_id': 'b' * 64}))
        for role in ('sdist', 'pyz'):
            (directory / names[role]).write_bytes(b'controlled artifact')
        return wheel, directory / names['sdist']
    monkeypatch.setattr(capture_ci_build, 'build_release', build)
    path = tmp_path / 'build.json'
    result = capture_ci_build.capture(path, commit='c' * 40)
    assert result == json.loads(path.read_bytes())
    assert result['format_version'] == result['test_report_format'] == 2
    assert result['commit'] == 'c' * 40 and result['commit_source'] == 'docker-build-context'
    assert result['binding'] == binding
    assert {row['role']: row['name'] for row in result['artifacts']} == artifact_names('1.4.0')
    assert all(row['size'] > 0 and len(row['sha256']) == 64 for row in result['artifacts'])
    with pytest.raises(FileExistsError): capture_ci_build.capture(path, commit='c' * 40)
