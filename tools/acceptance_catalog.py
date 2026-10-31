"""Development-only acceptance catalogue shared by CI generation and review."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('acceptance-catalog.json').read_text(encoding='utf-8'))
if CATALOG['format_version'] != 1:
    raise ValueError('Unsupported acceptance catalogue')
WINDOWS_TESTS = tuple(CATALOG['windows_tests'])
PROOFS = {row['id']: row for row in CATALOG['proofs']}
if len(PROOFS) != len(CATALOG['proofs']):
    raise ValueError('Duplicate acceptance proof ID')
for proof in PROOFS.values():
    variants = proof['variants']
    if (not variants or len(set(variants)) != len(variants)
            or not set(proof['required_variants']) <= set(variants)
            or proof['scope'] not in ('all', 'windows', 'uv', 'full')):
        raise ValueError('Invalid acceptance proof variants or scope')


@dataclass(frozen=True)
class Lane:
    group: str
    name: str
    runner: str
    python: str
    platform: str
    windows_engine: str
    artifact: str
    suites: tuple[str, ...]
    ubuntu: str = ''

    @property
    def binding(self) -> tuple[str, str, str]:
        return self.platform, self.python, self.windows_engine

    def matrix(self) -> dict[str, str]:
        row = {key: getattr(self, key) for key in ('name', 'runner', 'python', 'windows_engine', 'artifact')}
        if self.ubuntu:
            row['ubuntu'] = self.ubuntu
        return row


def _lanes() -> tuple[Lane, ...]:
    rows = []
    full = tuple(CATALOG['full_suites'])
    for platform in CATALOG['native_platforms']:
        for python in platform.get('pythons', CATALOG['python_versions']):
            rows.append(Lane('acceptance', f"Release gate - {platform['label']} - Python {python}",
                             platform['runner'], python, platform['platform'], platform['windows_engine'],
                             f"patchharbor-packaging-{platform['runner']}-py{python}", full))
    platform = CATALOG['powershell7']
    for python in CATALOG['python_versions']:
        rows.append(Lane('windows-powershell7-acceptance',
                         f"Release gate - {platform['label']} - PowerShell 7 - Python {python}",
                         platform['runner'], python, platform['platform'], platform['windows_engine'],
                         f'patchharbor-windows-powershell7-py{python}', ('windows',)))
    docker = CATALOG['docker']
    for ubuntu in docker['ubuntu']:
        rows.append(Lane('ubuntu-docker-integration', f'Docker release gate - Ubuntu {ubuntu}',
                         docker['runner'], docker['python'], 'Linux', '',
                         f'patchharbor-docker-ubuntu-{ubuntu}', full, ubuntu))
    if len({row.name for row in rows}) != len(rows) or len({row.artifact for row in rows}) != len(rows):
        raise ValueError('Duplicate acceptance lane or artifact')
    return tuple(rows)


LANES = _lanes()
BY_ARTIFACT = {row.artifact: row for row in LANES}


def artifact_names(version: str) -> dict[str, str]:
    return {role: template.format(version=version) for role, template in CATALOG['artifact_roles'].items()}


def required_proofs(lane: Lane) -> frozenset[tuple[str, str]]:
    scopes = {'all'}
    if lane.platform == 'Windows':
        scopes.add('windows')
    if lane.platform == 'Linux' and lane.python == '3.14':
        scopes.add('uv')
    if lane.suites == tuple(CATALOG['full_suites']):
        scopes.add('full')
    return frozenset((proof['id'], variant) for proof in PROOFS.values()
                     if proof['scope'] in scopes for variant in proof['required_variants'])


def legacy_proofs(nodeids) -> dict[str, dict[str, str]]:
    """Frozen format-1 names; new evidence uses explicit IDs on the test itself."""
    nodes = set(nodeids)
    return {node: {'id': proof['id'], 'variant': variant}
            for proof in PROOFS.values() for variant in proof['variants']
            if (node := proof['legacy_format1_node'].format(variant=variant)) in nodes}
