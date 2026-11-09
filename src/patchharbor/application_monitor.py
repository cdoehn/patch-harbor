"""Read-only composition of the existing registry, configuration and Git readers."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from patchharbor.configuration import RepositoryConfigurationPaths, load_configuration
from patchharbor.errors import PatchHarborError
from patchharbor.git_commands import safe_git_queries
from patchharbor.monitor_types import MonitorExchange, MonitorRepository, MonitorSnapshot, observed_at
from patchharbor.registry import _parse_registry
from patchharbor.platform.filesystem import read_stable_regular_file_bounded
from patchharbor.repository import require_local_repository_identity
from patchharbor.safe_export_plan import inspect_source
from patchharbor.user_paths import registration_user_paths


def observe_repository(mapping, *, include_state=True) -> MonitorRepository:
    path, repo_id = mapping.repository_path.value, str(mapping.repo_id)
    result = MonitorRepository(repo_id, str(path), path.name, 'missing' if not path.is_dir() else 'ok', observed_at())
    if result.registration == 'missing':
        return replace(result, error='registered repository directory is missing')
    try:
        with safe_git_queries():
            require_local_repository_identity(mapping.repository_path, mapping.repo_id)
    except (PatchHarborError, OSError, ValueError, RuntimeError) as exc:
        return replace(result, registration='conflict', error=str(exc))
    try:
        read_stable_regular_file_bounded(path / '.patchharbor/config.json', max_bytes=1024 * 1024)
        configuration = load_configuration(RepositoryConfigurationPaths(mapping.repository_path, mapping.repo_id),
                                           validate_directory=False)
        result = replace(result, exchange=None if configuration.exchange_directory is None else str(configuration.exchange_directory),
                         archive=configuration.archive_directory)
        if not include_state:
            return result
        with safe_git_queries():
            source = inspect_source(path)
        if str(source.repo_id) != repo_id or source.repository.value != path:
            raise ValueError('repository mapping changed during observation')
        state = source.snapshot.state
        return replace(result, git_status='dirty' if state.dirty else 'clean',
                       commit=str(source.context.base_commit), fingerprint=source.context.state_fingerprint,
                       staged=len(state.staged), unstaged=len(state.unstaged), untracked=len(state.untracked))
    except (PatchHarborError, OSError, ValueError, RuntimeError) as exc:
        return replace(result, error=str(exc))


def monitor_snapshot(*, repository: str | None = None, exchange: Path | None = None, include_state: bool = True) -> MonitorSnapshot:
    stamp = observed_at()
    try:
        paths = registration_user_paths(create_configuration_directory=False, create_lock_directory=False)
        registry_bytes = read_stable_regular_file_bounded(paths.registry_path, max_bytes=4 * 1024 * 1024).content if paths.registry_path.exists() else None
        registry = _parse_registry(registry_bytes) if registry_bytes is not None else None
    except (PatchHarborError, OSError, ValueError, RuntimeError) as exc:
        return MonitorSnapshot(stamp, (), (), (str(exc),))
    mappings = registry.repositories if registry is not None else ()
    if len(mappings) > 256:
        return MonitorSnapshot(stamp, (), (), ('registry exceeds the observation limit of 256 repositories',))
    if repository is not None:
        wanted = str(Path(repository).expanduser().resolve())
        mappings = tuple(m for m in mappings if str(m.repo_id) == repository or str(m.repository_path) == wanted)
        if not mappings:
            return MonitorSnapshot(stamp, (), (), ('repository selector is not registered',))
    rows = tuple(observe_repository(m, include_state=include_state) for m in mappings)
    if exchange is not None:
        wanted_exchange = str(exchange.expanduser().resolve())
        rows = tuple(r for r in rows if r.exchange == wanted_exchange)
    owners: dict[str, list[str]] = {}
    for row in rows:
        if row.exchange is not None:
            owners.setdefault(row.exchange, []).append(row.repo_id)
    exchanges = []
    for path, ids in sorted(owners.items()):
        available = Path(path).is_dir()
        exchanges.append(MonitorExchange(path, tuple(ids), available, stamp,
                         None if available else 'exchange directory is unavailable'))
    try:
        after = read_stable_regular_file_bounded(paths.registry_path, max_bytes=4 * 1024 * 1024).content if paths.registry_path.exists() else None
        if after != registry_bytes:
            raise ValueError('registry changed during observation')
    except (OSError, ValueError, RuntimeError) as exc:
        rows = tuple(replace(r, git_status='unknown', error=str(exc)) for r in rows)
        return MonitorSnapshot(stamp, rows, tuple(exchanges), (str(exc),))
    return MonitorSnapshot(stamp, rows, tuple(exchanges))
