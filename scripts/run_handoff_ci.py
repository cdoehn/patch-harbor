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
from tools.acceptance_catalog import LANES, BY_ARTIFACT, artifact_names
from tools.acceptance_evidence import evaluate_proofs

REPOSITORY = "cdoehn/patch-harbor"
WORKFLOW = "acceptance-tests.yml"
BRANCH = "dev"
ARTIFACTS = {lane.artifact: lane.binding for lane in LANES}
JOBS = {lane.name for lane in LANES}

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
    require(type(document.get('format_version')) is int and document['format_version'] in (1, 2)
            and document.get('commit') == commit,
            'build evidence commit mismatch')
    if document['format_version'] == 2:
        require(document.get('test_report_format') == 2, 'invalid required test report format')
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
    names = artifact_names(version)
    require(len(artifacts) == len(names) and {row['name'] for row in artifacts} == set(names.values()),
            'build artifact inventory incomplete')
    if document['format_version'] == 2:
        require({row.get('role'): row['name'] for row in artifacts} == names, 'build artifact roles differ')
    require(all(type(row['size']) is int and row['size'] > 0 and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                for row in artifacts), 'build artifact hashes missing')
    return document


def artifact_evidence(artifact, expected, *, commit):
    lane = BY_ARTIFACT[artifact['name']]
    require(expected == lane.binding, 'artifact lane binding differs')
    raw = request(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    require(len(raw) <= 32 * 1024 * 1024, 'CI artifact exceeds compressed budget')
    docker = bool(lane.ubuntu)
    with ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        suites = lane.suites
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
        reports, documents = [], {}
        for suite in suites:
            name = f'patchharbor-{suite}-tests.json'
            data = archive.read(name)
            document = json.loads(data)
            signature = validate(document)
            require(document['expected_workers'] > 0, 'parallel test evidence required')
            require(document['binding'] == build['binding'], 'CI build/test inputs or interpreter differ')
            require(document['format_version'] == build['format_version'], 'build/test report format mismatch')
            documents[name] = document
            counts = Counter(outcome for _, outcome, _ in signature[2])
            counts['skipped'] += len(signature[1])
            reports.append({'name': name, 'sha256': sha256(data).hexdigest(), 'binding': document['binding'],
                            'workers': document['expected_workers'], 'counts': dict(counts),
                            'nodeids': signature[0], 'skips': [row for row in signature[2] if row[1] == 'skipped'],
                            'collection_skips': signature[1]})
        proofs = evaluate_proofs(documents, lane)
        return {'name': artifact['name'], 'id': artifact['id'], 'sha256': sha256(raw).hexdigest(),
                'bytes': len(raw), 'build': build, 'reports': reports, 'proofs': proofs}


def run(commit, run_id, *, workspace=None, attempt=1):
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'full Git commit required')
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0, 'numeric run and attempt required')
    workspace = workspace or ROOT / 'build' / 'manual-ci-review' / f'{run_id}-{attempt}'
    workspace.mkdir(parents=True, mode=0o700, exist_ok=False)
    receipt = workspace / 'evidence.json'
    evidence = {'format_version': 3, 'repository': REPOSITORY, 'workflow': WORKFLOW,
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
