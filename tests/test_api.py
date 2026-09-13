"""Public library contracts, not console rendering tests."""
from __future__ import annotations

from io import BytesIO, StringIO
import os
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace

import pytest

from patchharbor import api
import patchharbor.application as application
from patchharbor.progress import activity, observe_activity
from tests.platform_support import project_environment


def test_public_import_has_no_cli_environment_or_stream_side_effects(tmp_path: Path) -> None:
    script = """
import os, signal, sys
cwd, environment = os.getcwd(), dict(os.environ)
streams = sys.stdin, sys.stdout, sys.stderr
handler = signal.getsignal(signal.SIGINT)
from patchharbor import api
assert 'patchharbor.cli' not in sys.modules
assert 'patchharbor.presentation' not in sys.modules
assert 'patchharbor_watcher.cli' not in sys.modules
assert os.getcwd() == cwd and dict(os.environ) == environment
assert (sys.stdin, sys.stdout, sys.stderr) == streams
assert signal.getsignal(signal.SIGINT) == handler
assert len(api.__all__) == len(set(api.__all__))
assert all(hasattr(api, name) for name in api.__all__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=project_environment(),
        capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == completed.stderr == b""


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("method", [api.apply, api.apply_next, api.run])
def test_nonfinite_or_nonpositive_timeout_is_rejected_before_core(
    timeout: float, method, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("invalid API input must not reach Core")
    monkeypatch.setattr(application, "run_apply_path", forbidden)
    monkeypatch.setattr(application, "run_script_path", forbidden)
    with pytest.raises(ValueError):
        if method is api.run:
            method("source.sh", timeout=timeout)
        else:
            method(timeout=timeout)


@pytest.mark.parametrize("timeout", [True, "1", None, object()])
def test_timeout_requires_number_not_coercible_text(timeout: object) -> None:
    with pytest.raises(TypeError):
        api.apply(timeout=timeout)


@pytest.mark.parametrize("path", [b"repo", 7, None])
def test_repository_paths_are_text_pathlikes(path: object) -> None:
    with pytest.raises(TypeError):
        api.context(path)


@pytest.mark.parametrize("path", ["", "repo\x00name"])
def test_empty_or_nul_path_is_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        api.context(path)


def test_conflicting_apply_targets_are_rejected() -> None:
    with pytest.raises(ValueError):
        api.apply("some.zip", repository="another-repo")


def test_manual_and_automatic_apply_share_core_but_keep_distinct_scopes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = []
    report = object()
    def fake(path, **kwargs):
        calls.append((path, kwargs))
        return report
    monkeypatch.setattr(application, "run_apply_path", fake)
    assert api.apply(repository=tmp_path) is report
    assert calls[-1][0] is None
    assert calls[-1][1]["current_directory"] == tmp_path
    assert not calls[-1][1].get("automatic", False)
    assert api.apply_next(dry_run=True) is report
    assert calls[-1][1]["automatic"] is True
    assert calls[-1][1]["dry_run"] is True
    assert "current_directory" not in calls[-1][1]
    assert api.dry_run("candidate.zip") is report
    assert calls[-1][0] == Path("candidate.zip")
    assert calls[-1][1]["dry_run"] is True


def test_library_observer_is_explicit_and_request_scope_restores_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer, inner = [], []
    marker = object()
    def fake(path):
        activity("CORE", "fact")
        return marker
    monkeypatch.setattr(application, "repository_context", fake)
    with observe_activity(outer.append):
        assert api.context() is marker  # default must not inherit outer's observer
        assert outer == []
        assert api.context(observer=inner.append) is marker
        activity("OUTER", "restored")
        def raising(path):
            activity("CORE", "before failure")
            raise RuntimeError("original failure")
        monkeypatch.setattr(application, "repository_context", raising)
        with pytest.raises(RuntimeError, match="original failure"):
            api.context(observer=inner.append)
        activity("OUTER", "after failure")
    assert [event.phase for event in outer] == ["OUTER", "OUTER"]
    assert [event.phase for event in inner] == ["CORE", "CORE"]


def test_progress_callback_errors_do_not_turn_into_domain_failures(monkeypatch) -> None:
    def observer(event):
        raise RuntimeError("observer only")
    def fake(path):
        activity("CORE", "fact")
        return "result"
    monkeypatch.setattr(application, "repository_context", fake)
    assert api.context(observer=observer) == "result"


def test_keyboard_interrupt_is_not_hidden_by_api(monkeypatch) -> None:
    def fake(path):
        raise KeyboardInterrupt
    monkeypatch.setattr(application, "repository_context", fake)
    with pytest.raises(KeyboardInterrupt):
        api.context()


def test_output_sinks_are_explicit_and_passed_as_independent_channels(monkeypatch) -> None:
    seen = []
    text, raw, warnings = StringIO(), BytesIO(), StringIO()
    on_warning = lambda warning: None
    def fake(path, **kwargs):
        seen.append(kwargs["output"])
        return object()
    monkeypatch.setattr(application, "run_apply_path", fake)
    api.apply()
    assert seen[-1] is None
    api.apply(output=api.OutputStreams(text, raw, warnings, on_warning))
    sinks = seen[-1]
    assert sinks.live_text_stream is text
    assert sinks.raw_output_stream is raw
    assert sinks.warning_text_stream is warnings
    assert sinks.warning_observer is on_warning
    assert not any(sink.closed for sink in (text, raw, warnings))


@pytest.mark.parametrize("kwargs", [
    {"observer": 3}, {"output": StringIO()}, {"output": api.OutputStreams(text=object())},
    {"output": api.OutputStreams(on_warning=3)}, {"dry_run": 1},
])
def test_invalid_observer_output_or_switch_is_rejected(kwargs: dict) -> None:
    with pytest.raises(TypeError):
        api.apply(**kwargs)


def test_configuration_result_contains_persisted_settings(monkeypatch, tmp_path) -> None:
    settings = SimpleNamespace(exchange_directory=tmp_path, bundle_suffix=".txt", archive_directory="Archive")
    monkeypatch.setattr(application, "shared_configuration", lambda **kwargs: (tmp_path / "config.json", settings))
    result = api.configuration()
    assert result == api.ConfigurationResult(tmp_path / "config.json", tmp_path, ".txt", "Archive")


def test_relative_source_uses_explicit_cwd_without_chdir(monkeypatch, tmp_path) -> None:
    before = Path.cwd()
    observed = []
    def fake(path, **kwargs):
        observed.append((path, kwargs))
        return 124
    monkeypatch.setattr(application, "run_script_path", fake)
    result = api.run("job.sh", cwd=tmp_path)
    assert observed[-1][0] == tmp_path / "job.sh"
    assert observed[-1][1]["cwd"] == tmp_path
    assert Path.cwd() == before
    assert result.exit_code == 124
    assert not result.success  # child exit 124 is not a tool-timeout exception


def test_explicit_stream_uses_same_application_runner(monkeypatch, tmp_path) -> None:
    stream = StringIO("# PATCHHARBOR\nexit 0\n")
    seen = []
    def fake(source, **kwargs):
        seen.append((source, kwargs))
        return 0
    monkeypatch.setattr(application, "run_standard_input", fake)
    result = api.run(stream, cwd=tmp_path)
    assert result.success and seen[0][0] is stream
    assert not stream.closed
    with pytest.raises(TypeError):
        api.run(None)
