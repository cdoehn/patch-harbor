"""Installed-process API handoff and interruption, not console presentation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import zipfile

import pytest

from patchharbor import api
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from tests.platform_support import (
    IS_WINDOWS, assert_child_process_stopped, cleanup_test_processes,
    native_script, native_value, project_environment, wait_for_child_pid,
)
from tests.registration_support import create_repository, set_isolated_user_environment

pytestmark = pytest.mark.e2e


def _prepare(tmp_path, monkeypatch, posix_body, windows_body):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repo")
    context = api.register(repository)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange)
    entrypoint = native_value("run.sh", "run.ps1")
    package = exchange / "worker-package.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("patch.json", json.dumps({
            "marker": "patch-harbor", "format_version": 1,
            "repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm,
            "entrypoint": entrypoint,
        }))
        archive.writestr(entrypoint, native_script(posix_body, windows_body))
    return repository, exchange, context


def test_real_worker_does_not_import_cli_and_keeps_raw_script_output(tmp_path, monkeypatch):
    repository, exchange, context = _prepare(
        tmp_path, monkeypatch,
        "printf 'worker-stdout\\n'; printf 'worker-stderr\\n' >&2",
        "[Console]::Out.WriteLine('worker-stdout'); [Console]::Error.WriteLine('worker-stderr')",
    )
    # Use the actual worker while making any accidental CLI import a hard error.
    launcher = tmp_path / "no-cli-worker.py"
    launcher.write_text('''import importlib.abc
import sys
class NoCli(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {"patchharbor.cli", "patchharbor.presentation"}:
            raise AssertionError("worker imported console/CLI")
        return None
sys.meta_path.insert(0, NoCli())
from patchharbor_watcher.worker import main
raise SystemExit(main())
''', encoding="utf-8")
    completion = delegate_to_automatic_apply(
        apply_command=(sys.executable, str(launcher)), environment=project_environment(),
    )
    assert completion.process_exit_code == 0
    assert completion.invalid_response_text is None
    document = completion.apply_result
    assert document is not None and document["success"] is True
    assert document["result"]["repo_id"] == str(context.repo_id)
    bundle = Path(document["result"]["result_bundle"]["path"])
    assert bundle.parent == exchange.resolve()
    with zipfile.ZipFile(bundle) as archive:
        raw = archive.read("logs/execution.log")
        assert b"worker-stdout" in raw and b"worker-stderr" in raw
        run = json.loads(archive.read("logs/run.json"))
        assert run["primary_result"]["entrypoint_exit_code"] == 0
    assert api.context(repository).base_commit == context.base_commit


@pytest.mark.skipif(IS_WINDOWS, reason="direct POSIX SIGINT delivery to a worker")
def test_worker_interrupt_stops_script_and_publishes_failure_result(tmp_path, monkeypatch):
    repository, exchange, context = _prepare(
        tmp_path, monkeypatch,
        'printf "%s" "$$" > worker-child.pid\nwhile :; do sleep 1; done',
        "exit 0",  # this case exercises native POSIX signal delivery only
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "patchharbor_watcher.worker"],
        cwd=tmp_path, env=project_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    pid = None
    try:
        # Readiness, not a guessed sleep: don't interrupt before the child starts.
        pid = wait_for_child_pid(repository / "worker-child.pid", timeout=20)
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 130, stderr
        document = json.loads(stdout)
        assert document["process_exit_code"] == 130
        assert document["result"]["primary_result"]["interrupted"] is True
        assert_child_process_stopped(pid)
        bundle = Path(document["result"]["result_bundle"]["path"])
        assert bundle.parent == exchange.resolve()
        with zipfile.ZipFile(bundle) as archive:
            run = json.loads(archive.read("logs/run.json"))
            assert run["primary_result"]["interrupted"] is True
            assert run["repo_id"] == str(context.repo_id)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
        cleanup_test_processes(pid)
