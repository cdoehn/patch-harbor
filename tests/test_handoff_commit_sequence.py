"""Actual zero/one/multiple-commit handoffs in owned repositories and a local remote."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.result_reader import read_result_reference
from tests.platform_support import native_python_script, native_value
from tests.registration_support import create_repository, git

pytestmark = pytest.mark.e2e


def sequence(tmp_path, count, *, fail_phase=None):
    repo = create_repository(tmp_path / "repository")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "HEAD:refs/heads/main")
    api.register(repo)
    api.configure_exchange_directory(tmp_path / "exchange", repository=repo)
    context = api.context(repo)
    # Gates execute real checks against each fixture state. They are not nested
    # runs of PatchHarbor's own suite. Mode labels encode the supplied project
    # policy, while the outer project tests run with xdist.
    code = f"COUNT={count!r}\nFAIL_PHASE={fail_phase!r}\n" + r'''
import hashlib, json, subprocess, sys
from pathlib import Path
def run(*args, data=None):
    return subprocess.run(args, input=data, check=True, capture_output=True).stdout
def event(**value):
    print('PH_SEQUENCE_JSON=' + json.dumps(value), flush=True)
if COUNT == 0:
    event(action='diagnosis', content_sha256=hashlib.sha256(Path('tracked.txt').read_bytes()).hexdigest())
for phase in range(1, COUNT + 1):
    if phase > 1:
        delta = (f'diff --git a/tracked.txt b/tracked.txt\n--- a/tracked.txt\n+++ b/tracked.txt\n'
                 f'@@ -1 +1 @@\n-state {phase-1}\n+state {phase}\n').encode()
        run('git','apply','--check','-',data=delta)
        run('git','apply','-',data=delta)
    modes = ['serial', 'parallel'] if phase == COUNT else ['parallel']
    for mode in modes:
        expected = f'state {phase}\n'.encode()
        check = 'from pathlib import Path; assert Path("tracked.txt").read_bytes() == ' + repr(expected)
        if phase == FAIL_PHASE:
            check += '; raise SystemExit(29)'
        try:
            run(sys.executable, '-I', '-c', check)
        except subprocess.CalledProcessError:
            event(action='gate_failed', phase=phase, mode=mode)
            raise SystemExit(29)
        event(action='gate', phase=phase, mode=mode)
    run('git','add','--','tracked.txt')
    run('git','diff','--cached','--check')
    run('git','commit','-m',f'fixture phase {phase}')
    event(action='commit', phase=phase, sha=run('git','rev-parse','HEAD').decode().strip())
if COUNT:
    run('git','push','--no-follow-tags','--recurse-submodules=no','origin','HEAD:refs/heads/main')
    event(action='push', sha=run('git','rev-parse','HEAD').decode().strip())
'''
    body = native_python_script(code)
    entrypoint = native_value("run.sh", "run.ps1")
    patch = tmp_path / "handoff.zip"
    with ZipFile(patch, "w") as archive:
        archive.writestr("patch.json", json.dumps({
            "marker": "patch-harbor", "format_version": 1,
            **{key: str(getattr(context, key)) for key in
               ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
            "entrypoint": entrypoint,
        }))
        archive.writestr(entrypoint, body)
        if count: archive.writestr("tracked.txt", b"state 1\n")
    report = api.apply(patch)
    facts, digest = read_result_reference(report.result_bundle.path)
    with ZipFile(report.result_bundle.path) as archive:
        log = archive.read("logs/execution.log").decode()
    events = [json.loads(line.removeprefix("PH_SEQUENCE_JSON=")) for line in log.splitlines()
              if line.startswith("PH_SEQUENCE_JSON=")]
    return repo, remote, context, report, facts, events


@pytest.mark.parametrize("count", [0, 1, 3])
def test_real_diagnostic_and_commit_sequences_keep_gates_and_single_final_push(tmp_path, count):
    repo, remote, before, report, facts, events = sequence(tmp_path, count)
    assert report.process_exit_code == 0
    commits = [event for event in events if event["action"] == "commit"]
    assert len(commits) == count
    if count:
        expected = []
        for phase in range(1, count+1):
            for mode in (["serial", "parallel"] if phase == count else ["parallel"]):
                expected.append({"action": "gate", "phase": phase, "mode": mode})
            expected.append(commits[phase-1])
        expected.append({"action": "push", "sha": commits[-1]["sha"]})
        assert events == expected
        assert str(facts.completed_commit) == commits[-1]["sha"]
        assert git(repo, "rev-list", "--reverse", str(before.base_commit)+"..HEAD").stdout.splitlines() == [e["sha"] for e in commits]
    else:
        assert len(events) == 1 and events[0]["action"] == "diagnosis"
        assert str(facts.context.base_commit) == str(before.base_commit) and facts.completed_commit is None
    assert not facts.context.dirty and not git(repo, "status", "--porcelain").stdout
    assert git(repo, "ls-remote", "origin", "refs/heads/main").stdout.split()[0] == str(facts.context.base_commit)
    assert not git(repo, "ls-remote", "--tags", "origin").stdout


@pytest.mark.parametrize("fail_phase", [1, 2, 3])
def test_failed_gate_retains_real_partial_commits_and_never_pushes(tmp_path, fail_phase):
    repo, remote, before, report, facts, events = sequence(tmp_path, 3, fail_phase=fail_phase)
    assert report.process_exit_code == 29 and not facts.primary_result.success
    commits = [event for event in events if event["action"] == "commit"]
    assert len(commits) == fail_phase - 1
    assert facts.context.dirty and facts.completed_commit is None
    assert git(repo, "rev-list", "--reverse", str(before.base_commit)+"..HEAD").stdout.splitlines() == [e["sha"] for e in commits]
    assert str(facts.context.base_commit) == (commits[-1]["sha"] if commits else str(before.base_commit))
    assert (repo / "tracked.txt").read_bytes() == f"state {fail_phase}\n".encode()
    assert not git(repo, "diff", "--cached", "--name-only").stdout
    assert not any(e["action"] == "push" for e in events)
    assert events[-1] == {"action": "gate_failed", "phase": fail_phase,
                          "mode": "serial" if fail_phase == 3 else "parallel"}
    assert git(repo, "ls-remote", "origin", "refs/heads/main").stdout.split()[0] == str(before.base_commit)
