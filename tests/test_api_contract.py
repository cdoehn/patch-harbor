"""Compatibility of the public Python contract, not console presentation."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import inspect
from pathlib import Path
import typing

import pytest

from patchharbor import api
from tests.platform_support import PROJECT_ROOT


OPERATIONS = {
    "configuration": (),
    "configure_exchange_directory": ("directory",),
    "configure_bundle_suffix": ("suffix",),
    "configure_archive_directory": ("name",),
    "register": ("repository",),
    "context": ("repository",),
    "repositories": (),
    "unregister": ("selector",),
    "bundle": ("repository",),
    "apply": ("patch",),
    "dry_run": ("patch",),
    "apply_next": (),
    "run": ("source",),
}
PUBLIC_TYPES = {
    "ActivityEvent", "BundleResult", "CandidateSelector", "ConfigurationResult",
    "DirectoryCandidate", "ErrorKind", "FailureReason", "GitObjectFormat",
    "GitObjectId", "OutputStreams", "PackageFile", "PathInput", "PatchHarborError",
    "PrimaryResult", "PrimaryResultKind", "ProgressEvent", "ProgressObserver",
    "RegistryListResult", "RegistryRepository", "RegistryStatus", "RepositoryContext",
    "RepositoryId", "RepositoryPath", "RepositoryResolved", "RequestStarted",
    "ResultBundleResult", "ResultBundleStatus", "RunOperation", "RunReport", "RunTiming",
    "RunToolError", "ScriptPrepared", "ScriptResult", "UnregisterResult",
}


def test_v120_exports_remain_available_with_compatible_additions_allowed() -> None:
    required = set(OPERATIONS) | PUBLIC_TYPES | {"DEFAULT_TIMEOUT_SECONDS"}
    assert required <= set(api.__all__)
    assert len(api.__all__) == len(set(api.__all__))
    assert all(hasattr(api, name) for name in required)
    assert api.DEFAULT_TIMEOUT_SECONDS == 10800.0


@pytest.mark.parametrize("name,positional", list(OPERATIONS.items()))
def test_public_operation_call_shapes_and_annotations(name, positional) -> None:
    function = getattr(api, name)
    signature = inspect.signature(function)
    parameters = signature.parameters
    assert tuple(
        p.name for p in parameters.values()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ) == positional
    assert parameters["observer"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["observer"].default is None
    assert not any(p.kind in {p.VAR_POSITIONAL, p.VAR_KEYWORD} for p in parameters.values())
    annotations = typing.get_type_hints(function)
    assert set(parameters) <= set(annotations)
    assert "return" in annotations


def test_execution_and_configuration_defaults_are_explicit_and_stable() -> None:
    for function in (api.apply, api.apply_next, api.run):
        parameters = inspect.signature(function).parameters
        assert parameters["timeout"].default == api.DEFAULT_TIMEOUT_SECONDS
        assert parameters["output"].default is None
    assert inspect.signature(api.configuration).parameters["revalidate"].default is False
    assert inspect.signature(api.apply).parameters["repository"].default is None
    assert inspect.signature(api.run).parameters["select_candidate"].default is None
    assert inspect.signature(api.dry_run).parameters["output"].default is None


@pytest.mark.parametrize("name,required", [
    ("ConfigurationResult", {"path", "exchange_directory", "bundle_suffix", "archive_directory"}),
    ("UnregisterResult", {"repo_id", "repository_path"}),
    ("RepositoryContext", {"repo_id", "base_commit", "dirty", "state_fingerprint", "fingerprint_algorithm"}),
    ("OutputStreams", {"text", "raw", "warnings", "on_warning"}),
    ("ScriptResult", {"exit_code"}),
    ("RunToolError", {"kind", "message", "reason"}),
    ("RunReport", {"timing", "context", "primary_result", "result_bundle"}),
])
def test_public_result_facts_are_immutable_and_typed(name, required) -> None:
    cls = getattr(api, name)
    assert is_dataclass(cls)
    assert cls.__dataclass_params__.frozen
    assert required <= {field.name for field in fields(cls)}
    assert required <= set(typing.get_type_hints(cls))


def test_release_exposes_typing_metadata_without_runtime_dependencies() -> None:
    import tomllib
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["dependencies"] == []
    assert project["tool"]["setuptools"]["package-data"]["patchharbor"] == ["py.typed"]
    assert (PROJECT_ROOT / "src" / "patchharbor" / "py.typed").is_file()


def test_public_failure_keeps_semantic_information_and_diagnostics() -> None:
    diagnostic = Path("diagnostic-result.zip")
    report = object()
    error = api.PatchHarborError(
        "failure", api.FailureReason.STATE_MISMATCH,
        error_kind=api.ErrorKind.STATE_MISMATCH,
        emergency_diagnostics_path=diagnostic, run_report=report,
    )
    assert error.reason is api.FailureReason.STATE_MISMATCH
    assert error.error_kind is api.ErrorKind.STATE_MISMATCH
    assert error.emergency_diagnostics_path == diagnostic
    assert error.run_report is report
    assert api.ScriptResult(124).exit_code == 124
    assert api.ScriptResult(124).success is False
