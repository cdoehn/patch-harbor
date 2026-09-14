"""Real library operations with isolated user state and native interpreters."""
from __future__ import annotations

from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import zipfile

import pytest

from patchharbor import api
from tests.platform_support import native_script, native_value
from tests.registration_support import create_repository, git, set_isolated_user_environment

pytestmark = pytest.mark.e2e


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repository = create_repository(tmp_path / "repo")
    context = api.register(repository)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repository)
    return repository, context, exchange


def write_package(path: Path, context: api.RepositoryContext, *, exit_code: int = 0) -> None:
    entrypoint = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": "patch-harbor", "format_version": 1,
        "repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm, "entrypoint": entrypoint,
    }
    body = native_script(
        f"printf 'api-child\\n'; printf 'api-stderr\\n' >&2; exit {exit_code}",
        f"[Console]::Out.WriteLine('api-child'); [Console]::Error.WriteLine('api-stderr'); exit {exit_code}",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        archive.writestr(entrypoint, body)


def test_repository_configuration_and_bundle_are_structured_and_silent(
    workspace, capfd: pytest.CaptureFixture[str],
) -> None:
    repo, original, exchange = workspace
    assert api.context(repo) == original
    assert api.repositories().repositories[0].status is api.RegistryStatus.OK
    assert api.configuration(repo).exchange_directory == exchange.resolve()
    assert api.configure_bundle_suffix(".txt", repository=repo).bundle_suffix == ".txt"
    assert api.configure_archive_directory("", repository=repo).archive_directory == ""
    bundled = api.bundle(repo)
    assert bundled.context == original
    assert bundled.path.exists() and bundled.path.name.endswith(".zip.txt")
    with zipfile.ZipFile(bundled.path) as archive:
        context = json.loads(archive.read("context.json"))
        assert context["repo_id"] == str(original.repo_id)
        assert context["base_commit"] == str(original.base_commit)
        assert context["state_fingerprint"] == original.state_fingerprint
        assert archive.read("base/tracked.txt") == b"base\n"
    assert bundled.report.success and not bundled.report.execution_present
    removed = api.unregister(original.repo_id)
    assert removed.repo_id == original.repo_id and repo.exists()
    assert api.repositories().repositories == ()
    with pytest.raises(api.PatchHarborError) as caught:
        api.context(repo)
    assert caught.value.error_kind is api.ErrorKind.REPOSITORY_RESOLUTION_ERROR
    captured = capfd.readouterr()
    assert captured.out == captured.err == ""  # silence is a library I/O contract


def test_new_id_registration_is_explicit_and_path_unregister_accepts_cwd(workspace) -> None:
    repo, original, _ = workspace
    assert api.register(repo).repo_id == original.repo_id
    replaced = api.register(repo, new_id=True)
    assert replaced.repo_id != original.repo_id
    result = api.unregister(repo.name, cwd=repo.parent)
    assert result.repo_id == replaced.repo_id
    assert (repo / "tracked.txt").read_bytes() == b"base\n"


def test_apply_preserves_complete_raw_log_report_and_full_events(workspace, capfd) -> None:
    repo, context, exchange = workspace
    patch = exchange / "candidate.zip"
    write_package(patch, context)
    text, raw = StringIO(), BytesIO()
    events = []
    report = api.apply(
        patch, output=api.OutputStreams(text=text, raw=raw), observer=events.append,
    )
    assert report.success and report.primary_result.entrypoint_exit_code == 0
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED
    assert report.context is not None and report.context.repo_id == context.repo_id
    assert any(isinstance(event, api.RequestStarted) for event in events)
    resolved = [event for event in events if isinstance(event, api.RepositoryResolved)]
    assert resolved and resolved[0].context.base_commit == context.base_commit
    with zipfile.ZipFile(report.result_bundle.path) as archive:
        assert archive.read("logs/execution.log") == raw.getvalue()
        assert b"api-child" in raw.getvalue() and b"api-stderr" in raw.getvalue()
        assert json.loads(archive.read("logs/run.json"))["process_exit_code"] == 0
    assert "api-child" in text.getvalue() and "api-stderr" in text.getvalue()
    assert not text.closed and not raw.closed
    captured = capfd.readouterr()
    assert captured.out == captured.err == ""


def test_explicit_raw_sink_failure_cannot_truncate_mandatory_result_log(workspace) -> None:
    _, context, exchange = workspace
    patch = exchange / "sink-failure.zip"
    write_package(patch, context)
    class BrokenSink:
        def write(self, data):
            raise OSError("caller destination unavailable")
        def flush(self):
            pass
    report = api.apply(patch, output=api.OutputStreams(raw=BrokenSink()))
    assert not report.success
    assert report.primary_result.failure_reason is api.FailureReason.EXECUTION_ERROR
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED
    with zipfile.ZipFile(report.result_bundle.path) as archive:
        log = archive.read("logs/execution.log")
        assert b"api-child" in log and b"api-stderr" in log


@pytest.mark.parametrize("code", [17, 124, 130])
def test_child_exit_codes_are_not_reclassified_as_tool_errors(workspace, code) -> None:
    _, context, exchange = workspace
    patch = exchange / "nonzero.zip"
    write_package(patch, context, exit_code=code)
    report = api.apply(patch)
    assert not report.success
    assert report.primary_result.entrypoint_exit_code == code
    assert report.primary_result.kind is api.PrimaryResultKind.ENTRYPOINT_EXIT
    assert report.primary_tool_error is None
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED


def test_repository_argument_scopes_manual_discovery_without_chdir(workspace, tmp_path, monkeypatch) -> None:
    repo, context, exchange = workspace
    other = create_repository(tmp_path / "other")
    other_context = api.register(other)
    api.configure_exchange_directory(exchange, repository=other)
    write_package(exchange / "local.zip", context)
    write_package(exchange / "foreign.zip", other_context)
    os.utime(exchange / "local.zip", ns=(1000000, 1000000))
    os.utime(exchange / "foreign.zip", ns=(2000000, 2000000))
    cwd = tmp_path / "outside"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    report = api.dry_run(repository=repo)
    assert report.success and report.dry_run
    assert report.context is not None and report.context.repo_id == context.repo_id
    assert not report.execution_present and not report.context.dirty
    assert Path.cwd() == cwd
    automatic = api.apply_next(dry_run=True)
    assert automatic.context is not None and automatic.context.repo_id == other_context.repo_id
    assert (exchange / "local.zip").exists() and (exchange / "foreign.zip").exists()


def test_state_mismatch_remains_reported_without_mutating_repository(workspace) -> None:
    repo, context, exchange = workspace
    patch = exchange / "mismatch.zip"
    write_package(patch, context)
    (repo / "tracked.txt").write_bytes(b"keep my changes\n")
    before = git(repo, "status", "--porcelain").stdout
    report = api.apply(patch)
    assert not report.success and not report.execution_present
    assert report.primary_result.kind is api.PrimaryResultKind.STATE_MISMATCH
    assert git(repo, "status", "--porcelain").stdout == before
    assert (repo / "tracked.txt").read_bytes() == b"keep my changes\n"
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED


def test_manual_failed_retry_and_automatic_no_retry_use_core_replay(workspace) -> None:
    repo, context, exchange = workspace
    patch = exchange / "retry.zip"
    write_package(patch, context, exit_code=17)
    first = api.apply(repository=repo)
    assert first.execution_present and first.primary_result.entrypoint_exit_code == 17
    automatic = api.apply_next()
    assert not automatic.execution_present
    assert not automatic.repository_resolved
    manual = api.apply(repository=repo)
    assert manual.execution_present and manual.primary_result.entrypoint_exit_code == 17
    assert first.run_id != manual.run_id


def test_successful_identity_is_not_replayed(workspace) -> None:
    repo, context, exchange = workspace
    write_package(exchange / "once.zip", context)
    assert api.apply(repository=repo).success
    again = api.apply(repository=repo)
    assert not again.success and not again.execution_present


def test_fs_runner_accepts_stream_directory_selector_and_never_prompts(tmp_path, capfd) -> None:
    cwd = tmp_path / "work"
    cwd.mkdir()
    body = native_script("exit 0", "exit 0")
    stream = StringIO(body)
    assert api.run(stream, cwd=cwd).success
    assert not stream.closed
    directory = tmp_path / "scripts"
    directory.mkdir()
    first = directory / native_value("a.sh", "a.ps1")
    second = directory / native_value("b.sh", "b.ps1")
    first.write_text(body, encoding="utf-8")
    second.write_text(native_script("exit 17", "exit 17"), encoding="utf-8")
    with pytest.raises(api.PatchHarborError) as caught:
        api.run(directory, cwd=cwd)
    assert caught.value.reason is api.FailureReason.USAGE_ERROR
    result = api.run(directory, cwd=cwd,
                     select_candidate=lambda candidates: next(c for c in candidates if c.path == first))
    assert result.success
    selected = api.DirectoryCandidate(cwd / "unoffered.sh", 0)
    with pytest.raises(api.PatchHarborError) as caught:
        api.run(directory, cwd=cwd, select_candidate=lambda candidates: selected)
    assert caught.value.reason is api.FailureReason.USAGE_ERROR
    result = api.run(second, cwd=cwd)
    assert not result.success and result.exit_code == 17
    assert not any(cwd.iterdir())
    captured = capfd.readouterr()
    assert captured.out == captured.err == ""
