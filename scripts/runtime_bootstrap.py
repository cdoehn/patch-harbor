"""Reviewed handoff example using an independently trusted Core, never the input wheel.

This is a repository tool, not a new public Core API/CLI. Inspect is read-only;
installation is a separate explicit operation. Without this trusted reader use
the documented previous handoff procedure, not code taken from an unknown wheel.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from patchharbor.errors import PatchHarborError
from patchharbor.patch_package import resolve_patch_package
from patchharbor.platform.filesystem import read_stable_regular_file_with_sha256
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import _parse_repository_payloads, parse_result_payloads, result_member_path
from patchharbor.zip_payloads import read_zip_payload_bytes


def _binding(value) -> dict[str, str]:
    return {key: str(getattr(value, key)) for key in
            ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")}


@dataclass(frozen=True)
class Assessment:
    reference: Path
    reference_sha256: str
    binding: dict[str, str]
    full_reference_valid: bool
    reason: str | None
    wheel_name: str | None = None
    wheel_sha256: str | None = None
    version: str | None = None
    wheel_bytes: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Bootstrap:
    assessment: Assessment
    status: str
    reason: str | None
    python: Path | None = None
    workspace: Path | None = None


def assess(reference: Path, *, trusted_source_sha256: str | None = None) -> Assessment:
    """Check repository evidence and runtime profile without importing input code.

    The trusted digest must come from an already trusted source/channel. A digest
    copied from the same unknown archive does not establish source trust.
    """
    reference = reference.resolve(strict=True)
    policy = DEFAULT_RESOURCE_POLICY
    if reference.stat().st_size > policy.max_input_artifact_bytes:
        raise ValueError("Result exceeds input budget")
    captured = read_stable_regular_file_with_sha256(
        reference, retained_content_limit=policy.max_input_artifact_bytes,
        allow_path_identity_fallback=True,
    )
    if captured.content is None:
        raise ValueError("Result exceeds input budget")
    if trusted_source_sha256 is not None and captured.sha256 != trusted_source_sha256:
        raise ValueError("trusted Result identity does not match")
    payloads = read_zip_payload_bytes(captured.content, policy=policy, path_normalizer=result_member_path)
    # Shared existing schema, inventory, blob/hash, run and context checks. This
    # result is deliberately labelled separately from native full validation.
    repository = _parse_repository_payloads(payloads)
    binding = _binding(repository.context)
    try:
        complete = parse_result_payloads(payloads)
    except (PatchHarborError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
        return Assessment(reference, captured.sha256, binding, False, "runtime_invalid")
    runtime = complete.runtime
    if complete.format_version == 3:
        return Assessment(reference, captured.sha256, binding, True,
                          "result_format_requires_pyz_bootstrap")
    if runtime is None or runtime.status != "embedded":
        return Assessment(reference, captured.sha256, binding, True,
                          runtime.reason if runtime is not None else "legacy_result_without_runtime")
    if trusted_source_sha256 is None:
        return Assessment(reference, captured.sha256, binding, True, "runtime_source_untrusted")
    wheel = next(entry.content for entry in payloads if entry.relative_path == runtime.wheel.path)
    return Assessment(reference, captured.sha256, binding, True, None, Path(runtime.wheel.path).name,
                      runtime.wheel.sha256, runtime.version, wheel)


def _environment(workspace: Path) -> dict[str, str]:
    # Do not forward session credentials, arbitrary PYTHONPATH, user pip config,
    # proxy settings or installer caches into a newly prepared environment.
    allowed = ("PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL", "TZ")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    private = workspace / "private"
    private.mkdir(exist_ok=True)
    for name in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
                 "APPDATA", "LOCALAPPDATA", "TMPDIR", "TEMP", "TMP"):
        environment[name] = str(private)
    environment.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_CONFIG_FILE=os.devnull)
    return environment


def _run(command: list[str], workspace: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=workspace, env=environment, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8", errors="strict")


def install(assessment: Assessment, workspace: Path, *, python: str = sys.executable,
            installer_python: str = sys.executable) -> Bootstrap:
    """One explicit offline attempt; technical unavailability selects the old path."""
    if assessment.reason is not None:
        return Bootstrap(assessment, "fallback", assessment.reason)
    # Keep verified immutable bytes; never reopen an extracted user wheel.
    if assessment.wheel_bytes is None or sha256(assessment.wheel_bytes).hexdigest() != assessment.wheel_sha256:
        raise ValueError("verified runtime bytes changed")
    workspace = workspace.absolute()
    stage = "workspace_unavailable"
    try:
        workspace.mkdir(mode=0o700)  # refuses existing/symlink destinations
        environment = _environment(workspace)
        wheel = workspace / assessment.wheel_name
        wheel.write_bytes(assessment.wheel_bytes)
        requirements = workspace / "requirements.txt"
        requirements.write_text(f"./{wheel.name} --hash=sha256:{assessment.wheel_sha256}\n", encoding="utf-8")
        target = workspace / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        stage = "venv_unavailable"
        commands = [([python, "-I", "-m", "venv", "--without-pip", str(workspace / "venv")], stage)]
        pip = [installer_python, "-I", "-m", "pip", "--python", str(target), "install", "--no-index",
               "--no-deps", "--only-binary=:all:", "--no-cache-dir", "--no-compile", "--require-hashes",
               "-r", str(requirements)]
        # pip checks the actual target interpreter's full Requires-Python before
        # installation. No ignore flag, build fallback or interpreter download.
        commands += [(pip + ["--dry-run"], "installer_or_python_incompatible"), (pip, "installation_failed")]
        for command, stage in commands:
            result = _run(command, workspace, environment)
            (workspace / (stage + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode:
                return Bootstrap(assessment, "fallback", stage, workspace=workspace)
        stage = "runtime_import_failed"
        probe = _run([str(target), "-I", "-B", "-c",
                      "import json,sys; from pathlib import Path; import patchharbor; from patchharbor import api; "
                      "assert Path(patchharbor.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); "
                      "assert callable(api.inspect_patch) and callable(api.validate_patch); "
                      "print(json.dumps({'version':patchharbor.__version__}))"], workspace, environment)
        if probe.returncode or json.loads(probe.stdout) != {"version": assessment.version}:
            return Bootstrap(assessment, "fallback", stage, workspace=workspace)
        return Bootstrap(assessment, "ready", None, target, workspace)
    except (OSError, ValueError, UnicodeError):
        return Bootstrap(assessment, "fallback", stage, workspace=workspace)


def check_patch(patch: Path, bootstrap: Bootstrap) -> dict[str, object]:
    """Check final patch bytes, retaining honest native vs previous-path evidence."""
    patch = patch.absolute()
    assessment = bootstrap.assessment
    current = assess(assessment.reference, trusted_source_sha256=assessment.reference_sha256)
    package = resolve_patch_package(patch)
    binding = _binding(package.manifest)
    if binding != current.binding:
        raise ValueError("patch/reference binding mismatch")
    method, reason = "previous_handoff", bootstrap.reason
    if bootstrap.status == "ready":
        try:
            result = _run([str(bootstrap.python), "-I", "-B", "-m", "patchharbor.cli", "validate", str(patch),
                           "--reference-bundle", str(assessment.reference), "--json"],
                          bootstrap.workspace, _environment(bootstrap.workspace))
            native = json.loads(result.stdout)
        except (OSError, ValueError, UnicodeError):
            reason = "native_tool_unavailable"
        else:
            if not isinstance(native, dict) or type(native.get("success")) is not bool:
                reason = "native_tool_unavailable"
            elif native["success"] is False:
                raise ValueError("native validation rejected the patch/reference")
            else:
                validation = native.get("result")
                if (result.returncode or not isinstance(validation, dict)
                        or not isinstance(validation.get("inspection"), dict)):
                    reason = "native_tool_unavailable"
                else:
                    if (validation.get("reference_sha256") != current.reference_sha256
                            or validation["inspection"].get("package_sha256") != package.package_sha256
                            or validation.get("binding_matches") is not True or validation.get("scope") != "reference"):
                        raise ValueError("native validation returned inconsistent evidence")
                    method, reason = "native_reference", None
    # No old success receipt is valid for changed final bytes.
    final = resolve_patch_package(patch)
    if final.package_sha256 != package.package_sha256:
        raise ValueError("final patch bytes changed; validation must be repeated")
    assess(assessment.reference, trusted_source_sha256=assessment.reference_sha256)
    return {"method": method, "reason": reason, "package_sha256": final.package_sha256,
            "package_size": patch.stat().st_size, "reference_sha256": current.reference_sha256,
            "binding": binding, "full_reference_valid": current.full_reference_valid,
            "native_validation": method == "native_reference"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--trusted-source-sha256")
    parser.add_argument("--install-in", type=Path)
    parser.add_argument("--patch", type=Path)
    arguments = parser.parse_args(argv)
    assessment = assess(arguments.reference, trusted_source_sha256=arguments.trusted_source_sha256)
    bootstrap = (install(assessment, arguments.install_in) if arguments.install_in is not None
                 else Bootstrap(assessment, "fallback", assessment.reason or "installation_not_requested"))
    document = {"reference_sha256": assessment.reference_sha256, "binding": assessment.binding,
                "full_reference_valid": assessment.full_reference_valid, "runtime_status": bootstrap.status,
                "reason": bootstrap.reason, "python": str(bootstrap.python) if bootstrap.python else None}
    if arguments.patch is not None:
        document["patch"] = check_patch(arguments.patch, bootstrap)
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
