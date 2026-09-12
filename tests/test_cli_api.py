"""Functional command routing and machine contracts; no presentation snapshots."""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

import patchharbor.api as api
import patchharbor.cli as cli
from tests.registration_support import create_repository, set_isolated_user_environment


class RoutedToApi(RuntimeError):
    pass


@pytest.mark.parametrize(("arguments", "function"), [
    (["configure", "show"], "configuration"),
    (["configure", "exchange-directory", "exchange"], "configure_exchange_directory"),
    (["configure", "bundle-suffix", ".txt"], "configure_bundle_suffix"),
    (["configure", "bundle-suffix", "--clear"], "configure_bundle_suffix"),
    (["configure", "archive-dir", "Archive"], "configure_archive_directory"),
    (["configure", "archive-dir", "--clear"], "configure_archive_directory"),
    (["register", "repo"], "register"),
    (["registry", "list", "--json"], "repositories"),
    (["unregister", "repo"], "unregister"),
    (["context", "repo", "--json"], "context"),
    (["bundle", "repo", "--json"], "bundle"),
    (["apply", "--json", "some.zip"], "apply"),
    (["apply", "--dry-run", "--json"], "apply"),
    (["apply", "--json", "--automatic"], "apply_next"),
    (["fs", "run", "script.sh"], "run"),
    (["fs", "run"], "run"),
])
def test_every_cli_operation_uses_public_api(monkeypatch, arguments, function) -> None:
    observed = []
    def operation(*args, **kwargs):
        observed.append((args, kwargs))
        raise RoutedToApi
    monkeypatch.setattr(api, function, operation)
    with pytest.raises(RoutedToApi):
        cli.main(arguments, stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    assert len(observed) == 1
    assert "observer" in observed[0][1]


@pytest.mark.parametrize("command", [["apply"], ["fs", "run"]])
@pytest.mark.parametrize("seconds", ["nan", "inf", "-inf"])
def test_cli_rejects_nonfinite_timeout_at_argument_boundary(command, seconds) -> None:
    with pytest.raises(SystemExit) as caught:
        cli.main([*command, f"--timeout={seconds}"], stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    assert caught.value.code == 2


def test_context_json_uses_identical_repository_values_as_public_api(tmp_path, monkeypatch) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    expected = api.register(repo)
    stdout = StringIO()
    code = cli.main(["context", str(repo), "--json"], stdout=stdout, stderr=StringIO())
    document = json.loads(stdout.getvalue())
    assert code == 0 and document["success"]
    assert document["result"]["repo_id"] == str(expected.repo_id)
    assert document["result"]["base_commit"] == str(expected.base_commit)
    assert document["result"]["state_fingerprint"] == expected.state_fingerprint


def test_api_error_reason_maps_to_existing_cli_json_status(monkeypatch) -> None:
    def error(*args, **kwargs):
        raise api.PatchHarborError("failure", api.FailureReason.REPOSITORY_ERROR,
                                   error_kind=api.ErrorKind.REPOSITORY_RESOLUTION_ERROR)
    monkeypatch.setattr(api, "context", error)
    stdout = StringIO()
    code = cli.main(["context", "--json"], stdout=stdout, stderr=StringIO())
    document = json.loads(stdout.getvalue())
    assert code == 8
    assert document["error"]["kind"] == "repository_resolution_error"
    assert document["error"]["patchharbor_error_code"] == 8
    assert document["process_exit_code"] == 8 and document["success"] is False
