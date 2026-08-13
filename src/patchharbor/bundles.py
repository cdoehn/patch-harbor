"""Resolve neutral input artifacts to ordered PatchHarbor bundles."""

from __future__ import annotations

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import (
    BundlePayload,
    BundleScript,
    InputArtifact,
    PatchBundle,
)
from patchharbor.parser import ScriptFormatError, validate_required_marker
from patchharbor.platform.errors import describe_os_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.zip_payloads import (
    InvalidZipArchiveError,
    NotZipArchiveError,
    ZipArchiveReadError,
    ZipResourceLimitError,
    is_zip_archive,
    read_zip_payloads,
)


_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _artifact_source_error(
    artifact: InputArtifact,
    detail: object,
) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read script source {artifact.display_name}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _zip_source_error(
    artifact: InputArtifact,
    detail: object,
) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read ZIP archive {artifact.display_name}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _invalid_zip_bundle(
    artifact: InputArtifact,
    detail: object,
) -> PatchHarborError:
    return _zip_source_error(artifact, f"invalid PatchBundle ({detail})")


def _zip_limit_error(
    artifact: InputArtifact,
    detail: str,
) -> PatchHarborError:
    return _zip_source_error(
        artifact,
        f"resource limit exceeded ({detail})",
    )


def _artifact_limit_error(
    artifact: InputArtifact,
    policy: ResourcePolicy,
) -> PatchHarborError:
    return _artifact_source_error(
        artifact,
        "resource limit exceeded "
        f"(input artifact exceeds {policy.max_input_artifact_bytes} bytes)",
    )


def _artifact_warnings(
    artifact: InputArtifact,
    policy: ResourcePolicy,
) -> tuple[str, ...]:
    """Validate the current artifact size and return its optional warning."""
    try:
        current_size = artifact.path.stat().st_size
    except OSError as exc:
        raise _artifact_source_error(artifact, describe_os_error(exc)) from exc
    if current_size > policy.max_input_artifact_bytes:
        raise _artifact_limit_error(artifact, policy)
    warning = policy.large_content_warning("input artifact", current_size)
    return () if warning is None else (warning,)


def _read_direct_artifact(
    artifact: InputArtifact,
    policy: ResourcePolicy,
) -> bytes:
    try:
        with artifact.path.open("rb") as stream:
            raw_content = stream.read(policy.max_input_artifact_bytes + 1)
    except OSError as exc:
        raise _artifact_source_error(artifact, describe_os_error(exc)) from exc
    if len(raw_content) > policy.max_input_artifact_bytes:
        raise _artifact_limit_error(artifact, policy)
    return raw_content


def _classify_zip_payloads(
    payloads: tuple[BundlePayload, ...],
    policy: ResourcePolicy,
) -> tuple[
    tuple[BundleScript, ...],
    tuple[BundlePayload, ...],
    tuple[str, ...],
]:
    scripts: list[BundleScript] = []
    files: list[BundlePayload] = []
    warnings: list[str] = []

    for payload in payloads:
        if warning := policy.large_content_warning(
            f"ZIP entry {payload.relative_path!r}",
            len(payload.content),
        ):
            warnings.append(warning)

        try:
            script_text = payload.content.decode("utf-8")
            validate_required_marker(script_text)
        except (UnicodeError, ScriptFormatError):
            files.append(payload)
            continue

        scripts.append(
            BundleScript(
                text=script_text,
                display_name=payload.relative_path,
            )
        )

    return tuple(scripts), tuple(files), tuple(warnings)


def _no_valid_zip_script(artifact: InputArtifact) -> PatchHarborError:
    return PatchHarborError(
        "no valid PatchHarbor scripts found in ZIP archive "
        f"{artifact.display_name}",
        ExitCode.NO_VALID_SCRIPT,
    )


def _try_direct_script(
    raw_content: bytes,
    artifact: InputArtifact,
) -> tuple[BundleScript | None, PatchHarborError | None, bool]:
    try:
        script_text = raw_content.decode("utf-8")
    except UnicodeError as exc:
        return None, _artifact_source_error(artifact, exc), False

    try:
        validate_required_marker(script_text)
    except ScriptFormatError as exc:
        return (
            None,
            PatchHarborError(str(exc), ExitCode.NO_VALID_SCRIPT),
            True,
        )

    return (
        BundleScript(
            text=script_text,
            display_name=artifact.display_name,
        ),
        None,
        True,
    )


def _resolve_zip_bundle(
    artifact: InputArtifact,
    policy: ResourcePolicy,
    artifact_warnings: tuple[str, ...],
) -> PatchBundle:
    try:
        raw_payloads = read_zip_payloads(artifact.path, policy=policy)
    except ZipResourceLimitError as exc:
        raise _zip_limit_error(artifact, str(exc)) from exc
    except InvalidZipArchiveError as exc:
        raise _invalid_zip_bundle(artifact, exc) from exc
    except (NotZipArchiveError, ZipArchiveReadError) as exc:
        raise _zip_source_error(artifact, exc) from exc

    scripts, payloads, entry_warnings = _classify_zip_payloads(
        raw_payloads,
        policy,
    )
    if not scripts:
        raise _no_valid_zip_script(artifact)
    return PatchBundle(
        scripts=scripts,
        payloads=payloads,
        warnings=artifact_warnings + entry_warnings,
    )


def resolve_patch_bundle(
    artifact: InputArtifact,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchBundle:
    """Resolve one source-neutral artifact to an ordered PatchBundle."""
    artifact_warnings = _artifact_warnings(artifact, policy)
    if is_zip_archive(artifact.path):
        return _resolve_zip_bundle(artifact, policy, artifact_warnings)

    raw_content = _read_direct_artifact(artifact, policy)
    direct_script, direct_error, direct_was_utf8 = _try_direct_script(
        raw_content,
        artifact,
    )
    if direct_script is not None:
        return PatchBundle(
            scripts=(direct_script,),
            warnings=artifact_warnings,
        )
    assert direct_error is not None

    zip_hint = (
        artifact.path.suffix.lower() == ".zip"
        or raw_content.startswith(_ZIP_SIGNATURES)
    )
    if zip_hint:
        return _resolve_zip_bundle(artifact, policy, artifact_warnings)
    if direct_was_utf8:
        raise direct_error
    raise PatchHarborError(
        "file is neither a UTF-8 PatchHarbor script nor a ZIP archive: "
        f"{artifact.display_name}",
        ExitCode.NO_VALID_SCRIPT,
    )
