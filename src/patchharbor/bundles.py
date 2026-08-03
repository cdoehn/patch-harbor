"""Resolve neutral input artifacts to ordered PatchHarbor bundles."""

from __future__ import annotations

from dataclasses import dataclass
import stat
import zipfile

from patchharbor.bundle_paths import (
    BundlePathError,
    validate_bundle_member_paths,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import (
    BundlePayload,
    BundleScript,
    InputArtifact,
    PatchBundle,
)
from patchharbor.parser import ScriptFormatError, validate_required_marker
from patchharbor.platform.errors import describe_os_error


CONTENT_WARNING_BYTES = 10 * 1024 * 1024
MAX_INPUT_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_ENTRY_BYTES = 256 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 512 * 1024 * 1024
_ZIP_READ_CHUNK_BYTES = 64 * 1024
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


@dataclass(frozen=True)
class _ValidatedZipMember:
    entry: zipfile.ZipInfo
    relative_path: str
    is_directory: bool


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


def _artifact_limit_error(artifact: InputArtifact) -> PatchHarborError:
    return _artifact_source_error(
        artifact,
        "resource limit exceeded "
        f"(input artifact exceeds {MAX_INPUT_ARTIFACT_BYTES} bytes)",
    )


def _large_content_warning(label: str, size_bytes: int) -> str | None:
    if size_bytes > CONTENT_WARNING_BYTES:
        return f"{label} is large ({size_bytes} bytes)"
    return None


def _validate_artifact_budget(artifact: InputArtifact) -> None:
    if artifact.size_bytes > MAX_INPUT_ARTIFACT_BYTES:
        raise _artifact_limit_error(artifact)
    try:
        current_size = artifact.path.stat().st_size
    except OSError as exc:
        raise _artifact_source_error(artifact, describe_os_error(exc)) from exc
    if current_size > MAX_INPUT_ARTIFACT_BYTES:
        raise _artifact_limit_error(artifact)


def _read_direct_artifact(artifact: InputArtifact) -> bytes:
    try:
        with artifact.path.open("rb") as stream:
            raw_content = stream.read(MAX_INPUT_ARTIFACT_BYTES + 1)
    except OSError as exc:
        raise _artifact_source_error(artifact, describe_os_error(exc)) from exc
    if len(raw_content) > MAX_INPUT_ARTIFACT_BYTES:
        raise _artifact_limit_error(artifact)
    return raw_content


def _validate_zip_budgets(
    artifact: InputArtifact,
    entries: list[zipfile.ZipInfo],
) -> None:
    if len(entries) > MAX_ZIP_ENTRIES:
        raise _zip_limit_error(
            artifact,
            f"more than {MAX_ZIP_ENTRIES} entries",
        )

    total_bytes = 0
    for entry in entries:
        if entry.file_size > MAX_ZIP_ENTRY_BYTES:
            raise _zip_limit_error(
                artifact,
                f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
            )
        total_bytes += entry.file_size
        if total_bytes > MAX_ZIP_TOTAL_BYTES:
            raise _zip_limit_error(
                artifact,
                f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
            )


def _zip_member_is_directory(
    entry: zipfile.ZipInfo,
    *,
    artifact: InputArtifact,
) -> bool:
    if entry.create_system != 3:
        return entry.is_dir()

    file_type = stat.S_IFMT(entry.external_attr >> 16)
    if entry.is_dir():
        if file_type not in (0, stat.S_IFDIR):
            raise _invalid_zip_bundle(
                artifact,
                f"unsupported entry type for {entry.filename!r}",
            )
        return True

    if file_type not in (0, stat.S_IFREG):
        raise _invalid_zip_bundle(
            artifact,
            f"unsupported entry type for {entry.filename!r}",
        )
    return False


def _validate_zip_members(
    entries: list[zipfile.ZipInfo],
    *,
    artifact: InputArtifact,
) -> tuple[_ValidatedZipMember, ...]:
    member_kinds = tuple(
        (
            entry,
            _zip_member_is_directory(entry, artifact=artifact),
        )
        for entry in entries
    )
    try:
        normalized_paths = validate_bundle_member_paths(
            (entry.filename, is_directory)
            for entry, is_directory in member_kinds
        )
    except BundlePathError as exc:
        raise _invalid_zip_bundle(artifact, exc) from exc

    return tuple(
        _ValidatedZipMember(
            entry=entry,
            relative_path=relative_path,
            is_directory=is_directory,
        )
        for (entry, is_directory), relative_path in zip(
            member_kinds,
            normalized_paths,
            strict=True,
        )
    )


def _read_zip_entry(
    archive: zipfile.ZipFile,
    member: _ValidatedZipMember,
    *,
    artifact: InputArtifact,
    total_bytes_read: int,
) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    entry_bytes_read = 0

    with archive.open(member.entry, "r") as stream:
        while chunk := stream.read(_ZIP_READ_CHUNK_BYTES):
            entry_bytes_read += len(chunk)
            total_bytes_read += len(chunk)
            if entry_bytes_read > MAX_ZIP_ENTRY_BYTES:
                raise _zip_limit_error(
                    artifact,
                    f"entry {member.relative_path!r} exceeds "
                    f"{MAX_ZIP_ENTRY_BYTES} bytes",
                )
            if total_bytes_read > MAX_ZIP_TOTAL_BYTES:
                raise _zip_limit_error(
                    artifact,
                    f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
                )
            chunks.append(chunk)

    return b"".join(chunks), total_bytes_read


def _read_zip_members(
    archive: zipfile.ZipFile,
    *,
    artifact: InputArtifact,
) -> tuple[
    tuple[BundleScript, ...],
    tuple[BundlePayload, ...],
    tuple[str, ...],
]:
    entries = archive.infolist()
    _validate_zip_budgets(artifact, entries)
    members = _validate_zip_members(entries, artifact=artifact)
    total_bytes_read = 0
    scripts: list[BundleScript] = []
    payloads: list[BundlePayload] = []
    warnings: list[str] = []

    for member in members:
        if member.is_directory:
            continue

        raw_content, total_bytes_read = _read_zip_entry(
            archive,
            member,
            artifact=artifact,
            total_bytes_read=total_bytes_read,
        )
        if warning := _large_content_warning(
            f"ZIP entry {member.relative_path!r}",
            len(raw_content),
        ):
            warnings.append(warning)

        try:
            script_text = raw_content.decode("utf-8")
            validate_required_marker(script_text)
        except (UnicodeError, ScriptFormatError):
            payloads.append(
                BundlePayload(
                    relative_path=member.relative_path,
                    content=raw_content,
                )
            )
            continue

        scripts.append(
            BundleScript(
                text=script_text,
                display_name=member.relative_path,
            )
        )

    return tuple(scripts), tuple(payloads), tuple(warnings)


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


def _resolve_zip_bundle(artifact: InputArtifact) -> PatchBundle:
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            scripts, payloads, entry_warnings = _read_zip_members(
                archive,
                artifact=artifact,
            )
    except zipfile.BadZipFile as exc:
        raise _zip_source_error(artifact, exc) from exc
    except PatchHarborError:
        raise
    except OSError as exc:
        raise _zip_source_error(artifact, describe_os_error(exc)) from exc
    except RuntimeError as exc:
        raise _zip_source_error(artifact, exc) from exc

    if not scripts:
        raise _no_valid_zip_script(artifact)
    return PatchBundle(
        scripts=scripts,
        payloads=payloads,
        warnings=artifact.warnings + entry_warnings,
    )


def resolve_patch_bundle(artifact: InputArtifact) -> PatchBundle:
    """Resolve one source-neutral artifact to an ordered PatchBundle."""
    _validate_artifact_budget(artifact)
    if zipfile.is_zipfile(artifact.path):
        return _resolve_zip_bundle(artifact)

    raw_content = _read_direct_artifact(artifact)
    direct_script, direct_error, direct_was_utf8 = _try_direct_script(
        raw_content,
        artifact,
    )
    if direct_script is not None:
        return PatchBundle(
            scripts=(direct_script,),
            warnings=artifact.warnings,
        )
    assert direct_error is not None

    zip_hint = (
        artifact.path.suffix.lower() == ".zip"
        or raw_content.startswith(_ZIP_SIGNATURES)
    )
    if zip_hint:
        return _resolve_zip_bundle(artifact)
    if direct_was_utf8:
        raise direct_error
    raise PatchHarborError(
        "file is neither a UTF-8 PatchHarbor script nor a ZIP archive: "
        f"{artifact.display_name}",
        ExitCode.NO_VALID_SCRIPT,
    )
