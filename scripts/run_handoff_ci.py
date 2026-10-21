"""Read-only acceptance review of an existing manually dispatched GitHub run.

No dispatch, rerun, push, or waiting. The historical filename is retained;
Christian starts CI himself and supplies its full commit and numeric Run-ID.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test_results import validate

REPOSITORY = "cdoehn/patch-harbor"
WORKFLOW = "acceptance-tests.yml"
BRANCH = "dev"
PYTHONS = ("3.10", "3.11", "3.12")
ARTIFACTS = {}
JOBS = set()
for runner, platform, label, engine, versions in (
    ("ubuntu-24.04", "Linux", "Ubuntu 24.04", "", PYTHONS),
    ("windows-2025", "Windows", "Windows 2025", "powershell.exe", PYTHONS),
    ("ubuntu-26.04", "Linux", "Ubuntu 26.04", "", ("3.14",)),
):
    for python in versions:
        ARTIFACTS[f"patchharbor-packaging-{runner}-py{python}"] = (platform, python, engine)
        JOBS.add(f"Release gate - {label} - Python {python}")
for python in PYTHONS:
    ARTIFACTS[f"patchharbor-windows-powershell7-py{python}"] = ("Windows", python, "pwsh")
    JOBS.add(f"Release gate - Windows 2025 - PowerShell 7 - Python {python}")
for ubuntu in ("24.04", "26.04"):
    ARTIFACTS[f"patchharbor-docker-ubuntu-{ubuntu}"] = ("Linux", "3.12", "")
    JOBS.add(f"Docker release gate - Ubuntu {ubuntu}")

DOCKER_FILES = {"00-build.log", "10-environment-preflight.log", "15-build-evidence.log",
                "20-core-and-architecture.log", "30-e2e-and-acceptance.log",
                "40-platform.log", "50-packaging.log", "summary.txt"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def request(route, body=None, *, binary=False):
    require(body is None, "read-only CI review cannot dispatch or mutate GitHub")
    command = ["gh", "api", "--hostname", "github.com", "--method",
               "GET", "-H", "X-GitHub-Api-Version: 2026-03-10",
               f"repos/{REPOSITORY}/{route}"]
    result = subprocess.run(command, input=None,
                            capture_output=True, check=True, timeout=120)
    if binary:
        return result.stdout
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(route, key):
    rows = []
    for page in range(1, 11):
        separator = "&" if "?" in route else "?"
        document = request(f"{route}{separator}per_page=100&page={page}")
        current = document[key]
        require(isinstance(current, list), "invalid GitHub page")
        rows.extend(current)
        if len(current) < 100:
            return rows
    raise ValueError("GitHub result exceeds pagination budget")


def save(path, document):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    print("PATCHHARBOR_CI_JSON=" + json.dumps(document, ensure_ascii=True), flush=True)


def _build_evidence(data, expected, commit, docker):
    document = json.loads(data)
    require(document.get('format_version') == 1 and document.get('commit') == commit,
            'build evidence commit mismatch')
    binding = document['binding']
    platform, python, engine = expected
    require(binding['platform'] == platform and binding['python'].startswith(python + '.')
            and binding['windows_engine'] == engine, 'build platform mismatch')
    require(document['commit_source'] == ('docker-build-context' if docker else 'checkout'),
            'build provenance mismatch')
    require(document['requires_python'] == '>=3.10' and re.fullmatch(r'[0-9a-f]{64}', document['pyz_content_id']),
            'build variant mismatch')
    dependencies = document['dependencies']
    require(all(isinstance(dependencies.get(name), str) and dependencies[name] for name in
                ('pip', 'setuptools', 'build', 'wheel', 'pipx', 'pytest', 'pytest-xdist', 'pytest-timeout')),
            'resolved build dependencies missing')
    require(python != '3.10' or bool(dependencies.get('tomli')), 'Python 3.10 TOML dependency missing')
    version = document['version']
    require(isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.+-]+)?', version),
            'invalid build version')
    artifacts = document['artifacts']
    require(len(artifacts) == 3 and {row['name'] for row in artifacts} == {
        f'patchharbor-{version}-py3-none-any.whl', f'patchharbor-{version}.tar.gz', f'patchharbor-{version}.pyz'},
        'build artifact inventory incomplete')
    require(all(type(row['size']) is int and row['size'] > 0 and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                for row in artifacts), 'build artifact hashes missing')
    return document


def _required_proofs(rows, platform, python, *, packaging):
    passed = {node for node, outcome, _ in rows if outcome == 'passed'}
    if packaging:
        for kind in ('full', 'diff', 'mixed'):
            require(f'tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply[{kind}]' in passed,
                    'missing own-instruction PYZ pack/Apply proof: ' + kind)
        for route in ('wheel', 'source', 'sdist'):
            require(f'tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations[{route}]' in passed,
                    'missing three-generation installation proof: ' + route)
        require('tests/test_packaging_e2e.py::test_release_distributions_run_after_pipx_installation' in passed,
                'missing installed CLI/API/watcher proof')
        require('tests/test_python_variants.py::test_built_reader_variant_bootstraps_and_packs_in_fresh_stdlib_process[>=3.10]' in passed,
                'missing stdlib-only Python 3.10 variant proof')
        if platform == 'Linux' and python == '3.14':
            require('tests/test_runtime_bootstrap.py::test_uv_installed_runtime_works_outside_checkout' in passed,
                    'missing designated uv proof')
    if platform == 'Windows':
        for file, name in (
            ('test_python_compat_windows', 'test_native_legacy_handle_adapter_detects_real_change_with_restored_mtime'),
            ('test_python_compat_windows', 'test_native_junction_is_rejected_without_new_pathlib_api'),
            ('test_python_compat_windows', 'test_native_private_request_dacl_is_protected_and_inherited[named]'),
            ('test_python_compat_windows', 'test_native_private_request_dacl_is_protected_and_inherited[random]'),
            ('test_bootstrap_python_compat', 'test_native_bootstrap_detects_same_size_restored_mtime_change'),
            ('test_bootstrap_python_compat', 'test_native_bootstrap_rejects_junction_parent_without_pathlib_api'),
            ('test_bootstrap_python_compat', 'test_native_bootstrap_prepares_private_inheriting_dacl'),
        ):
            require(f'tests/{file}.py::{name}' in passed, 'missing native Windows safety proof: ' + name)


def artifact_evidence(artifact, expected, *, commit):
    raw = request(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    require(len(raw) <= 32 * 1024 * 1024, 'CI artifact exceeds compressed budget')
    platform, python, engine = expected
    docker = artifact['name'].startswith('patchharbor-docker-')
    with ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        suites = ('windows',) if engine == 'pwsh' else ('core', 'e2e', 'platform', 'packaging')
        expected_names = {f'patchharbor-{suite}-tests.json' for suite in suites} | {'patchharbor-build.json'}
        if docker: expected_names |= DOCKER_FILES
        require(len(infos) == len(expected_names) and {row.filename for row in infos} == expected_names,
                'CI report inventory mismatch')
        require(sum(row.file_size for row in infos) <= 128 * 1024 * 1024
                and all(row.file_size <= 32 * 1024 * 1024 and not row.flag_bits & 1 for row in infos),
                'CI report exceeds budget or is encrypted')
        build = _build_evidence(archive.read('patchharbor-build.json'), expected, commit, docker)
        if docker:
            summary = dict(line.split('=', 1) for line in archive.read('summary.txt').decode().splitlines())
            require(summary['status'] == '0' and summary['stage'] == 'packaging tests'
                    and artifact['name'].endswith(summary['ubuntu_version']), 'Docker gate did not finish')
        reports, all_rows = [], []
        for suite in suites:
            name = f'patchharbor-{suite}-tests.json'
            data = archive.read(name)
            document = json.loads(data)
            signature = validate(document)
            require(document['expected_workers'] > 0, 'parallel test evidence required')
            require(document['binding'] == build['binding'], 'CI build/test inputs or interpreter differ')
            all_rows.extend(signature[2])
            counts = Counter(outcome for _, outcome, _ in signature[2])
            counts['skipped'] += len(signature[1])
            reports.append({'name': name, 'sha256': sha256(data).hexdigest(), 'binding': document['binding'],
                            'workers': document['expected_workers'], 'counts': dict(counts),
                            'nodeids': signature[0], 'skips': [row for row in signature[2] if row[1] == 'skipped'],
                            'collection_skips': signature[1]})
        _required_proofs(all_rows, platform, python, packaging=True)
        if engine != 'pwsh':
            for count in (0, 1, 3):
                node = f'tests/test_handoff_commit_sequence.py::test_real_diagnostic_and_commit_sequences_keep_gates_and_single_final_push[{count}]'
                require(any(row[0] == node and row[1] == 'passed' for row in all_rows), 'missing zero/one/multiple commit proof')
        return {'name': artifact['name'], 'id': artifact['id'], 'sha256': sha256(raw).hexdigest(),
                'bytes': len(raw), 'build': build, 'reports': reports}


def run(commit, run_id, *, workspace=None, attempt=1):
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'full Git commit required')
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0, 'numeric run and attempt required')
    workspace = workspace or ROOT / 'build' / 'manual-ci-review' / f'{run_id}-{attempt}'
    workspace.mkdir(parents=True, mode=0o700, exist_ok=False)
    receipt = workspace / 'evidence.json'
    evidence = {'format_version': 2, 'repository': REPOSITORY, 'workflow': WORKFLOW,
                'commit': commit, 'branch': BRANCH, 'run_id': run_id, 'run_attempt': attempt,
                'status': 'reviewing', 'dispatch_attempts': 0, 'jobs': [], 'artifacts': []}
    save(receipt, evidence)
    try:
        workflow = request(f'actions/workflows/{WORKFLOW}')
        observed = request(f'actions/runs/{run_id}')
        expected = {'id': run_id, 'head_sha': commit, 'head_branch': BRANCH,
                    'event': 'workflow_dispatch', 'workflow_id': workflow['id'], 'run_attempt': attempt}
        mismatches = {key: {'expected': value, 'observed': observed.get(key)}
                      for key, value in expected.items() if observed.get(key) != value}
        evidence.update(url=observed.get('html_url'), observed_run=observed,
                        binding_verified=not mismatches, binding_mismatches=mismatches)
        require(not mismatches, 'CI run binding mismatch: ' + ', '.join(sorted(mismatches)))
        if observed['status'] != 'completed':
            evidence['status'] = 'pending'; save(receipt, evidence); return evidence
        jobs = pages(f'actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
        evidence['jobs'] = jobs
        require(observed['conclusion'] == 'success' and len(jobs) == len(JOBS)
                and {row['name'] for row in jobs} == JOBS
                and all(row['status'] == 'completed' and row['conclusion'] == 'success' and row['head_sha'] == commit for row in jobs),
                'incomplete or failed twelve-job CI matrix')
        artifacts = pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
        evidence['available_artifacts'] = artifacts
        for name, expected_platform in ARTIFACTS.items():
            matches = [row for row in artifacts if row['name'] == name and not row['expired']]
            require(len(matches) == 1, 'missing or duplicate CI report: ' + name)
            evidence['artifacts'].append(artifact_evidence(matches[0], expected_platform, commit=commit))
        require(len({row['build']['version'] for row in evidence['artifacts']}) == 1,
                'CI jobs built different product versions')
        final = request(f'actions/runs/{run_id}')
        require(all(final.get(key) == value for key, value in expected.items())
                and final['status'] == 'completed' and final['conclusion'] == 'success',
                'CI run changed during review')
        evidence['status'] = 'success'; save(receipt, evidence); return evidence
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, subprocess.SubprocessError) as exc:
        evidence.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
        save(receipt, evidence)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--workspace', type=Path)
    args = parser.parse_args(argv)
    result = run(args.commit, args.run_id, attempt=args.attempt, workspace=args.workspace)
    return 0 if result['status'] == 'success' else 2


if __name__ == '__main__':
    raise SystemExit(main())
