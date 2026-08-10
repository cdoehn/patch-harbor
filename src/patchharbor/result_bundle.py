"""Materialize one manual PatchHarbor Result Bundle."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import stat
from time import monotonic
from uuid import UUID, uuid4
import zipfile

from patchharbor.errors import result_bundle_error
from patchharbor.git_commands import nul_records, run_git_bytes
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    GitObjectFormat,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.physical_paths import physically_canonicalize
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_local_registration, inspect_repository_root
from patchharbor.repository_paths import (
    RepositoryRelativePath,
    validate_repository_paths,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


_RESULT_MARKER = "patch-harbor-result-bundle"
_RESULT_FORMAT_VERSION = 1
_SUPPORTED_BASE_MODES = frozenset((b"100644", b"100755"))


@dataclass(frozen=True)
class ManualResultBundle:
    """One successfully created manual Result Bundle."""

    run_id: UUID
    context: RepositoryContext
    path: Path


@dataclass(frozen=True)
class _BaseEntry:
    path: RepositoryRelativePath
    mode: bytes
    object_id: bytes
    content: bytes


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _require_registered_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository: RepositoryPath,
) -> None:
    id_matches = tuple(
        mapping for mapping in snapshot.repositories if mapping.repo_id == repo_id
    )
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == repository
    )
    if len(id_matches) != 1 or id_matches[0].repository_path != repository:
        raise result_bundle_error("repository identity is not registered for this path")
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise result_bundle_error("repository path has conflicting registrations")


def _registered_identity(
    paths: RegistrationUserPaths,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise result_bundle_error("repository has no local PatchHarbor identity")
    _require_registered_mapping(load_registry(paths), repo_id, repository)
    return repo_id


def _validate_object_id(
    value: bytes,
    object_format: GitObjectFormat,
) -> bytes:
    if len(value) != object_format.object_id_hex_length or any(
        byte not in b"0123456789abcdef" for byte in value
    ):
        raise result_bundle_error("git returned an invalid base object name")
    return value


def _read_base_tree(
    repository: RepositoryPath,
    context: RepositoryContext,
) -> tuple[tuple[RepositoryRelativePath, bytes, bytes], ...]:
    raw = run_git_bytes(
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        str(context.base_commit),
        cwd=repository.value,
    )
    parsed: list[tuple[bytes, bytes, bytes]] = []
    for record in nul_records(raw, "base tree"):
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.split(b" ", 2)
        except ValueError as exc:
            raise result_bundle_error("git returned malformed base tree data") from exc
        if mode not in _SUPPORTED_BASE_MODES or object_type != b"blob":
            raise result_bundle_error("base tree contains an unsupported entry")
        parsed.append(
            (
                raw_path,
                mode,
                _validate_object_id(
                    object_id,
                    context.base_commit.object_format,
                ),
            )
        )

    paths = validate_repository_paths(entry[0] for entry in parsed)
    paths_by_bytes = {path.original_bytes: path for path in paths}
    if len(paths_by_bytes) != len(parsed):
        raise result_bundle_error("git returned ambiguous base tree paths")
    return tuple(
        (paths_by_bytes[raw_path], mode, object_id)
        for raw_path, mode, object_id in parsed
    )


def _read_base_blobs(
    repository: RepositoryPath,
    entries: tuple[tuple[RepositoryRelativePath, bytes, bytes], ...],
) -> tuple[_BaseEntry, ...]:
    if not entries:
        return ()
    response = run_git_bytes(
        "cat-file",
        "--batch",
        cwd=repository.value,
        input_bytes=b"".join(object_id + b"\n" for _, _, object_id in entries),
    )
    cursor = 0
    base_entries: list[_BaseEntry] = []
    for path, mode, expected_object_id in entries:
        header_end = response.find(b"\n", cursor)
        if header_end < 0:
            raise result_bundle_error("git returned malformed blob data")
        header = response[cursor:header_end]
        try:
            observed_object_id, object_type, raw_size = header.split(b" ", 2)
            size = int(raw_size)
        except (ValueError, OverflowError) as exc:
            raise result_bundle_error("git returned malformed blob data") from exc
        if (
            observed_object_id != expected_object_id
            or object_type != b"blob"
            or size < 0
        ):
            raise result_bundle_error("git returned an unexpected base object")

        content_start = header_end + 1
        content_end = content_start + size
        if content_end >= len(response) or response[content_end : content_end + 1] != b"\n":
            raise result_bundle_error("git returned truncated blob data")
        base_entries.append(
            _BaseEntry(
                path=path,
                mode=mode,
                object_id=expected_object_id,
                content=response[content_start:content_end],
            )
        )
        cursor = content_end + 1

    if cursor != len(response):
        raise result_bundle_error("git returned trailing blob data")
    return tuple(base_entries)


def _zip_info(name: str, *, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    permissions = 0o755 if executable else 0o644
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | permissions) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _default_result_directory(paths: RegistrationUserPaths) -> Path:
    directory = paths.result_directory
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return physically_canonicalize(directory, must_exist=True)
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error("cannot create the Result Bundle directory") from exc


def _write_bundle(
    path: Path,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_document: dict[str, object],
    base_entries: tuple[_BaseEntry, ...],
) -> None:
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            archive.writestr(_zip_info("manifest.json"), _json_bytes(manifest))
            archive.writestr(
                _zip_info("context.json"),
                _json_bytes(context_document),
            )
            archive.writestr(
                _zip_info("logs/run.json"),
                _json_bytes(run_document),
            )
            for entry in base_entries:
                archive.writestr(
                    _zip_info(
                        f"base/{entry.path.decoded}",
                        executable=entry.mode == b"100755",
                    ),
                    entry.content,
                )
    except (OSError, RuntimeError, ValueError, zipfile.LargeZipFile) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise result_bundle_error("cannot create the Result Bundle") from exc


def create_manual_result_bundle(path: Path) -> ManualResultBundle:
    """Create one base-only Result Bundle for a registered clean repository."""
    started = _utc_now()
    started_monotonic = monotonic()
    run_id = uuid4()
    paths = registration_user_paths()

    with ExitStack() as repository_scope:
        with registry_lock(paths):
            repository = inspect_repository_root(path)
            repo_id = _registered_identity(paths, repository)
            repository_scope.enter_context(repository_lock(paths, repo_id))

            locked_repository = inspect_repository_root(repository.value)
            if locked_repository != repository:
                raise result_bundle_error(
                    "repository path changed while acquiring its lock"
                )
            locked_id = _registered_identity(paths, locked_repository)
            if locked_id != repo_id:
                raise result_bundle_error(
                    "repository identity changed while acquiring its lock"
                )

        snapshot = capture_consistent_repository_snapshot(locked_repository)
        context = repository_context_from_snapshot(
            locked_repository,
            locked_id,
            snapshot,
        )
        if context.dirty:
            raise result_bundle_error(
                "base-only Result Bundles require a clean repository"
            )

        tree_entries = _read_base_tree(locked_repository, context)
        base_entries = _read_base_blobs(locked_repository, tree_entries)
        result_directory = _default_result_directory(paths)
        filename_timestamp = started.strftime("%Y%m%d_%H%M%S")
        result_path = result_directory / (
            f"patchharbor_result_{filename_timestamp}_{run_id}.zip"
        )

        ended = _utc_now()
        created_at = _timestamp(started)
        manifest = {
            "marker": _RESULT_MARKER,
            "format_version": _RESULT_FORMAT_VERSION,
            "created_at": created_at,
            "run_id": str(run_id),
            "repo_id": str(context.repo_id),
            "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm,
            "dirty": context.dirty,
            "dry_run": False,
            "execution_present": False,
            "primary_result": "success",
            "result_bundle_status": "created",
        }
        context_document = {
            "repo_id": str(context.repo_id),
            "base_commit": str(context.base_commit),
            "dirty": context.dirty,
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm,
            "created_at": created_at,
        }
        run_document = {
            "run_id": str(run_id),
            "operation": "bundle",
            "dry_run": False,
            "started_at": created_at,
            "ended_at": _timestamp(ended),
            "duration_seconds": max(0.0, monotonic() - started_monotonic),
            "repository_resolved": True,
            "repo_id": str(context.repo_id),
            "repository_path": str(context.repository_path),
            "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm,
            "execution_present": False,
            "primary_result": {
                "kind": "success",
                "success": True,
                "patchharbor_error_code": None,
                "entrypoint_started": False,
                "entrypoint_exit_code": None,
                "timed_out": False,
                "interrupted": False,
            },
            "result_bundle": {
                "attempted": True,
                "status": "created",
                "error": None,
            },
            "process_exit_code": 0,
        }
        _write_bundle(
            result_path,
            manifest=manifest,
            context_document=context_document,
            run_document=run_document,
            base_entries=base_entries,
        )

    return ManualResultBundle(run_id=run_id, context=context, path=result_path)
