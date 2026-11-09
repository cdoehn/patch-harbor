"""Private observation storage and read-only snapshots; no execution ownership."""
from datetime import datetime, timezone

from patchharbor.configuration import RepositoryConfigurationPaths, load_configuration
from patchharbor.monitor_live_schema import MAX_DOCUMENT, parse_live, _stamp
from patchharbor.monitor_types import observed_at
from patchharbor.platform.filesystem import PathKind, path_kind, read_stable_regular_file_bounded
from patchharbor.platform.monitor_process import process_identity
from patchharbor.registry import _parse_registry
from patchharbor.user_paths import raw_registration_user_paths


def observation_directory(paths):
    child = paths.state_directory / 'monitor-v1'
    if path_kind(child) not in (PathKind.MISSING, PathKind.DIRECTORY):
        raise ValueError('observation directory must not be linked')
    directory = child.resolve()
    if paths.registry_path.exists():
        registry = _parse_registry(read_stable_regular_file_bounded(paths.registry_path, max_bytes=4*1024*1024).content)
        if len(registry.repositories) > 256:
            raise ValueError('observation publisher registry limit exceeded')
        for mapping in registry.repositories:
            if not mapping.repository_path.value.is_dir():
                continue
            read_stable_regular_file_bounded(mapping.repository_path.value / '.patchharbor/config.json', max_bytes=1024*1024)
            config = load_configuration(RepositoryConfigurationPaths(mapping.repository_path, mapping.repo_id), validate_directory=False)
            exchange = config.exchange_directory
            if exchange is not None and (exchange == directory or exchange in directory.parents):
                raise ValueError('observation directory overlaps a configured Exchange')
    return directory


def prune_completed(directory):
    """Only recognized completed observations; never active runs or other state."""
    try:
        paths = []
        for index, path in enumerate(directory.iterdir()):
            if index >= 512:
                break
            if path_kind(path) is PathKind.REGULAR_FILE and path.name.startswith(('apply-', 'watcher-')) and path.suffix == '.json':
                paths.append(path)
        if len(paths) <= 128:
            return
        completed = []
        for path in paths:
            try:
                row = parse_live(read_stable_regular_file_bounded(path, max_bytes=MAX_DOCUMENT).content, path.name)
                if row['completed']:
                    completed.append((_stamp(row['updated_at']), path))
            except Exception:
                pass
        for _, path in sorted(completed, key=lambda item: (item[0], str(item[1])), reverse=True)[128:]:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def monitor_live(*, instance_id=None):
    result = {'format_version': 1, 'kind': 'patchharbor-monitor-live', 'observed_at': observed_at(),
              'instances': [], 'errors': [], 'incomplete': False}
    paths = raw_registration_user_paths()
    directory = paths.state_directory / 'monitor-v1'
    try:
        if path_kind(directory) is PathKind.MISSING:
            return result
        if path_kind(directory) is not PathKind.DIRECTORY:
            raise ValueError('observation directory is not a regular directory')
        candidates = []
        if instance_id is not None:
            candidates = [directory / (kind + '-' + instance_id + '.json') for kind in ('apply', 'watcher')]
            candidates = [path for path in candidates if path.exists()]
        else:
            for index, path in enumerate(directory.iterdir()):
                if index >= 512:
                    result['incomplete'] = True
                    break
                if path.name.endswith('.json') and path.name.startswith(('apply-', 'watcher-')):
                    candidates.append(path)
            candidates.sort(key=lambda p: p.lstat().st_mtime_ns, reverse=True)
        if len(candidates) > 64:
            result['incomplete'] = True
        for path in candidates[:64]:
            try:
                content = read_stable_regular_file_bounded(path, max_bytes=MAX_DOCUMENT).content
                row = parse_live(content, path.name)
                age = (datetime.now(timezone.utc) - _stamp(row['updated_at'])).total_seconds()
                current = process_identity(row['pid'])
                row['live'] = not row['completed'] and current is not None and current == row['process_identity'] and 0 <= age <= 15
                row['stale'] = not row['completed'] and not row['live']
                row['stale_reason'] = ('publisher identity unavailable or changed' if current is None or current != row['process_identity']
                                       else 'heartbeat expired or clock changed') if row['stale'] else None
                row['age_seconds'] = max(0, age)
                if instance_id is None:
                    row.pop('log_tail', None)
                result['instances'].append(row)
            except Exception as exc:
                result['errors'].append(path.name + ': ' + str(exc))
    except Exception as exc:
        result['errors'].append(str(exc))
    return result
