"""Synchronous Python facade for PatchHarbor (public since 1.2.0).

Import with ``from patchharbor import api``. Library requests are silent unless
an observer or output sinks are supplied. No CLI invocation, process-wide chdir,
implicit stdin, sys.exit, signal-handler installation or console rendering occurs
here. Git and trusted entrypoint subprocesses are still run by the existing Core.

``apply`` / ``apply_next`` / ``dry_run`` return a RunReport for known tool and
script failures, retaining the Result-Bundle outcome. Other operations raise
PatchHarborError for tool failures. Bad API argument types/values raise
TypeError/ValueError before Core work. Unexpected exceptions are not disguised.
The full contract and examples live in docs/python-api.md.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import TextIO

import patchharbor.application as _application
from patchharbor.api_types import (
    ActivityEvent, BundleResult, CandidateSelector, ConfigurationResult,
    DirectoryCandidate, GitObjectFormat, GitObjectId, OutputStreams, PackageFile,
    PrimaryResult, PrimaryResultKind, ProgressEvent, ProgressObserver,
    RegistryListResult, RegistryRepository, RegistryStatus, RepositoryContext,
    RepositoryId, RepositoryPath, RepositoryResolved, RequestStarted,
    ResultBundleResult, ResultBundleStatus, RunOperation, RunReport, RunTiming,
    RunToolError, ScriptPrepared, ScriptResult, UnregisterResult,
)
from patchharbor.errors import ErrorKind, FailureReason, PatchHarborError
from patchharbor.output import OutputTargets as _OutputTargets
from patchharbor.progress import observe_activity as _observe_activity


DEFAULT_TIMEOUT_SECONDS = _application.DEFAULT_TIMEOUT_SECONDS
PathInput = str | os.PathLike[str]

__all__ = [
    "ActivityEvent", "BundleResult", "CandidateSelector", "ConfigurationResult",
    "DEFAULT_TIMEOUT_SECONDS", "DirectoryCandidate", "ErrorKind", "FailureReason",
    "GitObjectFormat", "GitObjectId", "OutputStreams", "PackageFile", "PathInput",
    "PatchHarborError", "PrimaryResult", "PrimaryResultKind", "ProgressEvent",
    "ProgressObserver", "RegistryListResult", "RegistryRepository", "RegistryStatus",
    "RepositoryContext", "RepositoryId", "RepositoryPath", "RepositoryResolved",
    "RequestStarted", "ResultBundleResult", "ResultBundleStatus", "RunOperation",
    "RunReport", "RunTiming", "RunToolError", "ScriptPrepared", "ScriptResult",
    "UnregisterResult", "apply", "apply_next", "bundle", "configure_archive_directory",
    "configure_bundle_suffix", "configure_exchange_directory", "configuration",
    "context", "dry_run", "register", "repositories", "run", "unregister",
]


def _path(value: PathInput, name: str) -> Path:
    """Expand user notation but preserve symlinks for Core security checks."""
    raw = os.fspath(value)
    if not isinstance(raw, str):
        raise TypeError(f"{name} must be a text path, not bytes")
    if not raw or "\x00" in raw:
        raise ValueError(f"{name} must be a nonempty path without NUL")
    return Path(raw).expanduser()


def _optional_path(value: PathInput | None, name: str) -> Path | None:
    return None if value is None else _path(value, name)


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout must be a real number")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("timeout must be finite and greater than zero")
    return seconds


def _observer(value: ProgressObserver | None) -> ProgressObserver | None:
    if value is not None and not callable(value):
        raise TypeError("observer must be callable or None")
    return value


def _output(value: OutputStreams | None) -> _OutputTargets | None:
    if value is None:
        return None
    if not isinstance(value, OutputStreams):
        raise TypeError("output must be OutputStreams or None")
    for sink in (value.text, value.raw, value.warnings):
        if sink is not None and not all(callable(getattr(sink, attr, None))
                                        for attr in ("write", "flush")):
            raise TypeError("output sinks must provide write() and flush()")
    if value.on_warning is not None and not callable(value.on_warning):
        raise TypeError("on_warning must be callable or None")
    return _OutputTargets(
        live_text_stream=value.text, raw_output_stream=value.raw,
        warning_text_stream=value.warnings, warning_observer=value.on_warning,
    )


def _configuration_result(result: tuple[Path, _application.RepositoryConfiguration]) -> ConfigurationResult:
    path, settings = result
    return ConfigurationResult(
        path, settings.exchange_directory, settings.bundle_suffix,
        settings.archive_directory,
    )


def configuration(
    repository: PathInput = ".", *, revalidate: bool = False, observer: ProgressObserver | None = None,
) -> ConfigurationResult:
    """Read a registered repository's local settings; never create defaults.

    With revalidate=True, recheck the loaded physical Exchange target immediately
    before returning it (an explicit readiness check). This does not reserve the
    directory: each subsequent operation still performs its own safety checks.
    """
    if not isinstance(revalidate, bool):
        raise TypeError("revalidate must be boolean")
    path = _path(repository, "repository")
    with _observe_activity(_observer(observer)):
        return _configuration_result(_application.repository_configuration(path, revalidate=revalidate))


def configure_exchange_directory(
    directory: PathInput, *, repository: PathInput = ".", observer: ProgressObserver | None = None,
) -> ConfigurationResult:
    """Persist only the selected registered repository's Exchange directory."""
    path = _path(directory, "directory")
    target = _path(repository, "repository")
    with _observe_activity(_observer(observer)):
        return _configuration_result(_application.configure_exchange_directory(path, repository=target))


def configure_bundle_suffix(
    suffix: str, *, repository: PathInput = ".", observer: ProgressObserver | None = None,
) -> ConfigurationResult:
    """Set the literal suffix after .zip; an empty string clears it."""
    if not isinstance(suffix, str):
        raise TypeError("suffix must be text")
    target = _path(repository, "repository")
    with _observe_activity(_observer(observer)):
        return _configuration_result(_application.configure_bundle_suffix(suffix, repository=target))


def configure_archive_directory(
    name: str, *, repository: PathInput = ".", observer: ProgressObserver | None = None,
) -> ConfigurationResult:
    """Set the single archive child name; an empty string disables archival."""
    if not isinstance(name, str):
        raise TypeError("archive directory name must be text")
    target = _path(repository, "repository")
    with _observe_activity(_observer(observer)):
        return _configuration_result(_application.configure_archive_directory(name, repository=target))


def register(
    repository: PathInput = ".", *, new_id: bool = False,
    observer: ProgressObserver | None = None,
) -> RepositoryContext:
    """Register a clean repository; creating a new local identity is explicit."""
    path = _path(repository, "repository")
    if not isinstance(new_id, bool):
        raise TypeError("new_id must be boolean")
    with _observe_activity(_observer(observer)):
        return _application.register_repository(path, new_id=new_id)


def context(
    repository: PathInput = ".", *, observer: ProgressObserver | None = None,
) -> RepositoryContext:
    """Return full binding values and current dirty state of a registered repo."""
    path = _path(repository, "repository")
    with _observe_activity(_observer(observer)):
        return _application.repository_context(path)


def repositories(*, observer: ProgressObserver | None = None) -> RegistryListResult:
    """Return registered mappings and their observed consistency statuses."""
    with _observe_activity(_observer(observer)):
        return _application.registered_repositories()


def unregister(
    selector: PathInput | RepositoryId, *, cwd: PathInput = ".",
    observer: ProgressObserver | None = None,
) -> UnregisterResult:
    """Remove one mapping selected by UUID or repository path; never its files."""
    if isinstance(selector, RepositoryId):
        text = str(selector)
    else:
        text = os.fspath(selector)
        if not isinstance(text, str):
            raise TypeError("selector must be a text path or repository ID")
    if not text or "\x00" in text:
        raise ValueError("selector must be nonempty and contain no NUL")
    directory = _path(cwd, "cwd")
    with _observe_activity(_observer(observer)):
        repo_id, path = _application.unregister_repository(text, cwd=directory)
        return UnregisterResult(repo_id, path)


def bundle(
    repository: PathInput = ".", *, output_directory: PathInput | None = None,
    observer: ProgressObserver | None = None,
) -> BundleResult:
    """Publish a manual Result Bundle, using Exchange unless output is explicit."""
    path = _path(repository, "repository")
    destination = _optional_path(output_directory, "output_directory")
    with _observe_activity(_observer(observer)):
        result = _application.bundle_repository(path, output_directory=destination)
        return BundleResult(result.report)


def apply(
    patch: PathInput | None = None, *, repository: PathInput | None = None,
    dry_run: bool = False, output_directory: PathInput | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS, output: OutputStreams | None = None,
    observer: ProgressObserver | None = None,
) -> RunReport:
    """Apply one bound package, or discover the latest manual-retry candidate.

With no patch, repository (default current directory) scopes discovery. With an
explicit patch its manifest alone resolves the registered repository; supplying
repository as well is rejected instead of silently ignoring a target constraint.
Dry-run preserves the existing safety checks and Result-Bundle generation, but
never writes payloads, runs the entrypoint, consumes replay or archives bundles.
    """
    if patch is not None and repository is not None:
        raise ValueError("repository scopes discovery only; do not combine it with patch")
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be boolean")
    path = _optional_path(patch, "patch")
    directory = _optional_path(repository, "repository")
    destination = _optional_path(output_directory, "output_directory")
    seconds, targets = _timeout(timeout), _output(output)
    with _observe_activity(_observer(observer)):
        return _application.run_apply_path(
            path, dry_run=dry_run, output_directory=destination,
            timeout_seconds=seconds, output=targets, current_directory=directory,
        )


def dry_run(
    patch: PathInput | None = None, *, repository: PathInput | None = None,
    output_directory: PathInput | None = None, output: OutputStreams | None = None,
    observer: ProgressObserver | None = None,
) -> RunReport:
    """Validate via the same Apply boundary without executing the patch."""
    return apply(
        patch, repository=repository, dry_run=True, output_directory=output_directory,
        output=output, observer=observer,
    )


def apply_next(
    *, dry_run: bool = False, output_directory: PathInput | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS, output: OutputStreams | None = None,
    observer: ProgressObserver | None = None,
) -> RunReport:
    """One automatic poll of all repository-configured Exchange directories, never retrying a failed identity.

This is not a polling loop. The watcher/larger orchestrator owns that lifecycle.
The existing automatic Core path performs selection, revalidation, mutation and
attempt publication together; no candidate token escapes this boundary.
    """
    if not isinstance(dry_run, bool):
        raise TypeError("dry_run must be boolean")
    destination = _optional_path(output_directory, "output_directory")
    seconds, targets = _timeout(timeout), _output(output)
    with _observe_activity(_observer(observer)):
        return _application.run_apply_path(
            None, automatic=True, dry_run=dry_run, output_directory=destination,
            timeout_seconds=seconds, output=targets,
        )


def run(
    source: PathInput | TextIO, *, cwd: PathInput = ".",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    select_candidate: CandidateSelector | None = None,
    output: OutputStreams | None = None, observer: ProgressObserver | None = None,
) -> ScriptResult:
    """Execute the legacy fs-run path: script, ZIP, directory or explicit stream.

A directory with several candidates requires the caller's selector; the library
never prompts. For a relative source path, cwd is its base as well as the child's
working directory. Streams stay caller-owned. Tool failures raise PatchHarborError;
normal nonzero script exits are returned as ScriptResult(success=False).
    """
    directory = _path(cwd, "cwd").absolute()
    seconds, targets = _timeout(timeout), _output(output)
    actual_observer = _observer(observer)
    if select_candidate is not None and not callable(select_candidate):
        raise TypeError("select_candidate must be callable or None")
    is_path = isinstance(source, (str, os.PathLike))
    if is_path:
        path = _path(source, "source")
        if not path.is_absolute():
            path = directory / path
    elif not callable(getattr(source, "read", None)):
        raise TypeError("source must be a text path or a readable text stream")
    with _observe_activity(actual_observer):
        if is_path:
            exit_code = _application.run_script_path(
                path, cwd=directory, timeout_seconds=seconds,
                select_candidate=select_candidate, output=targets,
            )
        else:
            exit_code = _application.run_standard_input(
                source, cwd=directory, timeout_seconds=seconds, output=targets,
            )
        return ScriptResult(exit_code)
