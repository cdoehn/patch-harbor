"""Run real small pytest/xdist suites to exercise per-test/worker isolation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from xml.etree import ElementTree

import pytest

from tests.platform_support import PROJECT_ROOT


@pytest.mark.parametrize("workers", ["2", "4"])
def test_real_workers_have_disjoint_files_registry_and_locks(tmp_path: Path, workers: str) -> None:
    suite = tmp_path / "parallel-suite"
    suite.mkdir()
    output = tmp_path / "records"
    output.mkdir()
    (suite / "conftest.py").write_text('pytest_plugins = ["tests.conftest"]\n', encoding="utf-8")
    (suite / "test_workers.py").write_text(textwrap.dedent("""
        import json, os, pathlib
        import pytest
        from patchharbor.locks import registry_lock
        from patchharbor.user_paths import registration_user_paths
        from tests.registration_support import create_repository

        @pytest.mark.parametrize('number', range(16))
        def test_resources(number, tmp_path):
            paths = registration_user_paths()
            repository = create_repository(tmp_path / 'repository')
            with registry_lock(paths):
                paths.registry_path.write_text(str(number), encoding='utf-8')
                assert paths.registry_path.read_text(encoding='utf-8') == str(number)
            record = {'case': number, 'pid': os.getpid(),
                      'worker': os.environ['PYTEST_XDIST_WORKER'],
                      'registry': str(paths.registry_path), 'locks': str(paths.lock_directory),
                      'home': os.environ['HOME'], 'temp': os.environ['TMPDIR'],
                      'repository': str(repository)}
            # A unique file per test; no concurrent append to shared JSON.
            (pathlib.Path(os.environ['PH_TEST_RECORDS']) / f'{number}.json').write_text(json.dumps(record), encoding='utf-8')
    """), encoding="utf-8")
    report = tmp_path / "junit.xml"
    environment = os.environ.copy()
    environment["PH_TEST_RECORDS"] = str(output)
    environment["GIT_DIR"] = str(tmp_path / "not-a-repository")
    environment["GIT_TEMPLATE_DIR"] = str(tmp_path / "not-a-template")
    environment["PYTHONPATH"] = os.pathsep.join((str(PROJECT_ROOT), str(PROJECT_ROOT / "src")))
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools" / "run_tests.py"),
         "--workers", workers, "--", str(suite), "--junitxml", str(report)],
        cwd=tmp_path, env=environment, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    records = [json.loads(path.read_text(encoding="utf-8")) for path in output.glob("*.json")]
    assert {record["case"] for record in records} == set(range(16))
    assert len(records) == 16
    assert len({record["pid"] for record in records}) == int(workers)
    assert len({record["worker"] for record in records}) == int(workers)
    for key in ("registry", "locks", "home", "temp", "repository"):
        assert len({record[key] for record in records}) == 16
    document = ElementTree.parse(report)
    assert len(document.findall(".//testcase")) == 16
    assert not document.findall(".//failure")
    assert not document.findall(".//error")
