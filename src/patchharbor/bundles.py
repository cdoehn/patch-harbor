"""Resolve neutral input artifacts to ordered PatchHarbor bundles."""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import PurePosixPath
import stat
import zipfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import BundleScript, InputArtifact, PatchBundle
from patchharbor.parser import ScriptFormatError, validate_required_marker


MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_ENTRY_BYTES = 256 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 512 * 1024 * 1024
_ZIP_READ_CHUNK_BYTES = 64 * 1024
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _default_script_suffix() -> str:
    return ".ps1" if os.name == "nt" else ".sh"


def _direct_script_suffix(artifact: InputArtifact) -> str:
    return artifact.path.suffix or _default_script_suffix()


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


def _zip_limit_error(
    artifact: InputArtifact,
    detail: str,
) -> PatchHarborError:
    return _zip_source_error(
        artifact,
        f"resource limit exceeded ({detail})",
    )


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


def _is_regular_zip_entry(entry: zipfile.ZipInfo) -> bool:
    if entry.is_dir():
        return False

    if entry.create_system != 3:
        return True

    file_type = stat.S_IFMT(entry.external_attr >> 16)
    return file_type in (0, stat.S_IFREG)


def _read_zip_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
    *,
    artifact: InputArtifact,
    total_bytes_read: int,
) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    entry_bytes_read = 0

    with archive.open(entry, "r") as stream:
        while chunk := stream.read(_ZIP_READ_CHUNK_BYTES):
            entry_bytes_read += len(chunk)
            total_bytes_read += len(chunk)
            if entry_bytes_read > MAX_ZIP_ENTRY_BYTES:
                raise _zip_limit_error(
                    artifact,
                    f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
                )
            if total_bytes_read > MAX_ZIP_TOTAL_BYTES:
                raise _zip_limit_error(
                    artifact,
                    f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
                )
            chunks.append(chunk)

    return b"".join(chunks), total_bytes_read


def _iter_zip_scripts(
    archive: zipfile.ZipFile,
    *,
    artifact: InputArtifact,
) -> Iterator[BundleScript]:
    entries = archive.infolist()
    _validate_zip_budgets(artifact, entries)
    total_bytes_read = 0

    for entry in entries:
        if not _is_regular_zip_entry(entry):
            continue

        raw_content, total_bytes_read = _read_zip_entry(
            archive,
            entry,
            artifact=artifact,
            total_bytes_read=total_bytes_read,
        )
        if raw_content.startswith(_ZIP_SIGNATURES):
            continue

        try:
            script_text = raw_content.decode("utf-8")
            validate_required_marker(script_text)
        except (UnicodeError, ScriptFormatError):
            continue

        yield BundleScript(
            text=script_text,
            suffix=PurePosixPath(entry.filename).suffix
            or _default_script_suffix(),
        )


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
            suffix=_direct_script_suffix(artifact),
        ),
        None,
        True,
    )


def resolve_patch_bundle(artifact: InputArtifact) -> PatchBundle:
    """Resolve one source-neutral artifact to an ordered PatchBundle."""
    try:
        raw_content = artifact.path.read_bytes()
    except OSError as exc:
        raise _artifact_source_error(artifact, exc) from exc

    direct_script, direct_error, direct_was_utf8 = _try_direct_script(
        raw_content,
        artifact,
    )
    if direct_script is not None:
        return PatchBundle(scripts=(direct_script,))
    assert direct_error is not None

    zip_hint = (
        artifact.path.suffix.lower() == ".zip"
        or raw_content.startswith(_ZIP_SIGNATURES)
    )
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            scripts = tuple(_iter_zip_scripts(archive, artifact=artifact))
    except zipfile.BadZipFile as exc:
        if zip_hint:
            raise _zip_source_error(artifact, exc) from exc
        if direct_was_utf8:
            raise direct_error
        raise PatchHarborError(
            "file is neither a UTF-8 PatchHarbor script nor a ZIP archive: "
            f"{artifact.display_name}",
            ExitCode.NO_VALID_SCRIPT,
        ) from exc
    except PatchHarborError:
        raise
    except (OSError, RuntimeError) as exc:
        raise _zip_source_error(artifact, exc) from exc

    if not scripts:
        raise _no_valid_zip_script(artifact)
    return PatchBundle(scripts=scripts)
