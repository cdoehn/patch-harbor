"""Read-only preparation and complete revalidation of safe export boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from patchharbor.configuration import load_configuration
from patchharbor.configuration_context import configuration_paths_for_id
from patchharbor.errors import ErrorKind, LockBusyError, PatchHarborError
from patchharbor.git_commands import run_git_bytes, safe_git_queries
from patchharbor.locks import repository_lock_path
from patchharbor.models import RepositoryContext
from patchharbor.platform.filesystem import FileChangedDuringRead, FileReadLimitExceeded, read_stable_regular_file_with_sha256
from patchharbor.registry import load_registry
from patchharbor.repository_state import repository_context_from_snapshot
from patchharbor.result_bundle import _registered_identity
from patchharbor.resource_policy import ResultSnapshotLimitError
from patchharbor.runtime_profile import RuntimeLimitError
from patchharbor.safe_capture import safe_repository, safe_snapshot
from patchharbor.safe_export_paths import BoundDirectory
from patchharbor.safe_export_types import SafeExportError, SafeExportErrorCode, SafeExportPlan, require_host
from patchharbor.user_paths import registration_user_paths
from patchharbor.zip_payloads import ZipResourceLimitError


def converted_error(exc: BaseException, *, writing=False) -> SafeExportError:
    if isinstance(exc, SafeExportError):
        return exc
    code = SafeExportErrorCode.IO if writing else SafeExportErrorCode.REPOSITORY
    cause = exc
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, FileChangedDuringRead):
            code = SafeExportErrorCode.STALE
            break
        if isinstance(cause, (FileReadLimitExceeded, ResultSnapshotLimitError, ZipResourceLimitError, RuntimeLimitError)):
            code = SafeExportErrorCode.RESOURCE_LIMIT
            break
        if isinstance(cause, OSError):
            code = SafeExportErrorCode.IO
        cause = cause.__cause__
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        code = SafeExportErrorCode.INTERRUPTED
    if isinstance(exc, PatchHarborError) and exc.error_kind is ErrorKind.CONFIGURATION_ERROR:
        code = SafeExportErrorCode.CONFIGURATION
    return SafeExportError(code, str(exc) or code.value)


def file_digest(path: Path) -> str:
    return read_stable_regular_file_with_sha256(path, retained_content_limit=1,
                                               max_bytes=256 * 1024 * 1024).sha256


def source_facts(repository, paths, repo_id, configuration_paths):
    root = repository.value
    index = Path(run_git_bytes('rev-parse', '--git-path', 'index', cwd=root).decode().strip())
    head = Path(run_git_bytes('rev-parse', '--git-path', 'HEAD', cwd=root).decode().strip())
    return (file_digest(paths.registry_path), file_digest(configuration_paths.configuration_path),
            file_digest(root / '.patchharbor/id'), file_digest(root / index), file_digest(root / head),
            hashlib.sha256(run_git_bytes('for-each-ref', '--format=%(refname) %(objectname)', cwd=root)).hexdigest(),
            hashlib.sha256(run_git_bytes('config', '--null', '--list', cwd=root)).hexdigest())


@dataclass(frozen=True)
class PreparedSource:
    repository: object
    repo_id: object
    registry: object
    paths: object
    configuration_paths: object
    configuration: object
    snapshot: object
    context: RepositoryContext
    facts: tuple


def inspect_source(path: Path) -> PreparedSource:
    paths = registration_user_paths(create_configuration_directory=False, create_lock_directory=False)
    if not paths.registry_path.is_file():
        raise SafeExportError(SafeExportErrorCode.REPOSITORY, 'an existing repository registry is required')
    registry_digest = file_digest(paths.registry_path)
    registry = load_registry(paths)
    repository = safe_repository(path)
    repo_id = _registered_identity(registry, repository)
    configuration_paths = configuration_paths_for_id(repo_id, registry)
    if not configuration_paths.configuration_path.is_file():
        raise SafeExportError(SafeExportErrorCode.CONFIGURATION, 'existing repository configuration is required')
    configuration_digest = file_digest(configuration_paths.configuration_path)
    configuration = load_configuration(configuration_paths, validate_directory=False)
    facts = source_facts(repository, paths, repo_id, configuration_paths)
    if facts[:2] != (registry_digest, configuration_digest):
        raise SafeExportError(SafeExportErrorCode.STALE, 'configuration changed while preparing safe observation')
    snapshot = safe_snapshot(repository)
    if source_facts(repository, paths, repo_id, configuration_paths) != facts:
        raise SafeExportError(SafeExportErrorCode.STALE, 'source metadata changed during safe observation')
    context = repository_context_from_snapshot(repository, repo_id, snapshot)
    return PreparedSource(repository, repo_id, registry, paths, configuration_paths,
                          configuration, snapshot, context, facts)


def safe_context(path: Path) -> RepositoryContext:
    require_host()
    try:
        with safe_git_queries():
            return inspect_source(path).context
    except (PatchHarborError, OSError, RuntimeError, KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SafeExportError):
            raise
        raise converted_error(exc) from exc


def _overlap(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def prepare_plan(path: Path, *, output_directory: Path | None = None,
                 expected_context: RepositoryContext | None = None) -> SafeExportPlan:
    require_host()
    if expected_context is not None and not isinstance(expected_context, RepositoryContext):
        raise TypeError('expected_context must be a RepositoryContext')
    try:
        with safe_git_queries():
            source = inspect_source(path)
            if expected_context is not None and source.context != expected_context:
                raise SafeExportError(SafeExportErrorCode.STALE, 'safe context no longer matches the approved context')
            output = output_directory if output_directory is not None else source.configuration.exchange_directory
            if output is None:
                raise SafeExportError(SafeExportErrorCode.CONFIGURATION, 'no safe export output is configured')
            try:
                with BoundDirectory(output) as destination, BoundDirectory(source.paths.lock_directory) as locks:
                    forbidden = [m.repository_path.value for m in source.registry.repositories]
                    forbidden += [source.paths.configuration_directory, source.paths.state_directory]
                    if any(_overlap(destination.path, p) for p in forbidden):
                        raise SafeExportError(SafeExportErrorCode.UNSAFE_PATH, 'safe export output overlaps protected state')
                    if any(_overlap(locks.path, m.repository_path.value) for m in source.registry.repositories):
                        raise SafeExportError(SafeExportErrorCode.UNSAFE_PATH, 'lock directory overlaps a repository')
                    lock_paths = (source.paths.registry_lock_path, repository_lock_path(source.paths, source.repo_id))
                    facts = (str(source.repository), str(destination.path), destination.identity,
                             str(locks.path), locks.identity,
                             tuple(str(getattr(source.context, key)) for key in
                                   ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')),
                             source.facts)
                    digest = hashlib.sha256(json.dumps(facts, separators=(',', ':')).encode()).hexdigest()
                    return SafeExportPlan(source.context, destination.path, destination.path, lock_paths,
                                          source.configuration.exchange_directory, False, digest, facts)
            except OSError as exc:
                raise SafeExportError(SafeExportErrorCode.UNSAFE_PATH, 'safe export requires existing unlinked operating directories') from exc
    except (PatchHarborError, OSError, RuntimeError, KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, (SafeExportError, LockBusyError)):
            raise
        raise converted_error(exc) from exc


def revalidate_plan(plan: SafeExportPlan, path: Path) -> PreparedSource:
    current = prepare_plan(path, output_directory=plan.output_directory)
    if current != plan:
        raise SafeExportError(SafeExportErrorCode.STALE, 'safe export state or operating boundary changed')
    source = inspect_source(path)
    if source.context != plan.context or source.facts != plan._facts[-1]:
        raise SafeExportError(SafeExportErrorCode.STALE, 'source changed during export preflight')
    return source
