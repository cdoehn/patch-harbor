"""Read-only Exchange facts; never execute, recover, lock or archive a package."""
from __future__ import annotations

from pathlib import Path

from patchharbor.application_monitor import monitor_snapshot
from patchharbor.application_exchange import _select_exchange_candidate
from patchharbor.errors import PatchHarborError
from patchharbor.exchange_state import ExchangeStateSnapshot, _parse_state
from patchharbor.models import RepositoryId, GitObjectId, GitObjectFormat
from patchharbor.monitor_types import observed_at
from patchharbor.platform.filesystem import PathKind, path_kind, read_stable_regular_file_bounded
from patchharbor.result_reader import ReferenceContext
from patchharbor.user_paths import registration_user_paths

from patchharbor.monitor_artifact_facts import artifact_fact, ArtifactCache, ERRORS, monitor_log
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM


def replay_snapshot():
    paths = registration_user_paths(create_configuration_directory=False, create_lock_directory=False)
    path = paths.exchange_state_path
    content = read_stable_regular_file_bounded(path, max_bytes=4*1024*1024).content if path.exists() else None
    return _parse_state(content) if content is not None else ExchangeStateSnapshot()


def monitor_artifacts(repository, *, include_archive=False):
    result = {'format_version': 1, 'kind': 'patchharbor-monitor-artifacts', 'observed_at': observed_at(),
              'artifacts': [], 'errors': [], 'incomplete': False, 'selected_candidate': None,
              'history_complete': False}
    snapshot = monitor_snapshot(repository=repository)
    if snapshot.errors or len(snapshot.repositories) != 1:
        result['errors'] = list(snapshot.errors) or ['select one registered repository']
        return result
    repo = snapshot.repositories[0]
    result.update(repo_id=repo.repo_id, repository_path=repo.path, exchange=repo.exchange)
    if not repo.exchange:
        result['errors'] = [repo.error or 'no configured Exchange']
        return result
    try:
        state = replay_snapshot()
        state_known = True
    except ERRORS as exc:
        state, state_known = ExchangeStateSnapshot(), False
        result['errors'].append('replay state: ' + str(exc))
    directory = Path(repo.exchange)
    directories = [(directory, False)]
    if include_archive and repo.archive:
        archive = directory / repo.archive
        if path_kind(archive) is PathKind.DIRECTORY:
            directories.append((archive, True))
        elif path_kind(archive) is not PathKind.MISSING:
            result['errors'].append('archive is not a regular directory')
    candidates, total, count = [], 0, 0
    cache = ArtifactCache()
    context = None
    if repo.commit is not None and repo.error is None:
        context = ReferenceContext(RepositoryId(repo.repo_id), repo.path,
                                  GitObjectId(repo.commit, GitObjectFormat.for_hex_length(len(repo.commit))),
                                  repo.git_status == 'dirty', repo.fingerprint, FINGERPRINT_ALGORITHM)
    for parent, archived in directories:
        try:
            paths = []
            for path in parent.iterdir():
                paths.append(path)
                if len(paths) > 1024:
                    result['incomplete'] = True
                    result['errors'].append('directory exceeds 1024 entry observation limit')
                    break
            paths.sort(key=lambda p: p.name)
        except OSError as exc:
            result['errors'].append(str(exc))
            continue
        for path in paths:
            try:
                if path_kind(path) is PathKind.DIRECTORY:
                    continue
            except OSError as exc:
                result['errors'].append(str(exc))
                continue
            count += 1
            try:
                total += path.lstat().st_size
            except OSError:
                pass
            if count > 256 or total > 256*1024*1024:
                result['incomplete'] = True
                result['errors'].append('Exchange observation limit reached; history and candidate selection incomplete')
                break
            row, artifact = artifact_fact(path, archived, state, cache)
            if row['error']:
                result['incomplete'] = True
            row['eligibility'] = 'not a patch'
            if artifact is not None and artifact.selection is not None:
                if archived:
                    reason = 'archived'
                elif str(artifact.selection.repo_id) != repo.repo_id:
                    reason = 'different repository'
                elif context is None:
                    reason = 'repository state unavailable'
                elif not artifact.selection.matches_context(context):
                    reason = 'commit or fingerprint mismatch'
                elif not state_known:
                    reason = 'replay state unavailable'
                elif row['replay_status'] is not None:
                    reason = 'replay blocks automatic apply: ' + row['replay_status']
                else:
                    reason = 'eligible (observation, not reserved)'
                    candidates.append(artifact)
                row['eligibility'] = reason
                row['manual_retry_possible'] = (state_known and not archived and context is not None
                                                and artifact.selection.matches_context(context)
                                                and row['replay_status'] == 'failed')
            result['artifacts'].append(row)
    try:
        if replay_snapshot() != state:
            raise ValueError('replay state changed during observation')
        after = monitor_snapshot(repository=repository).repositories
        if len(after) != 1 or any(getattr(after[0], k) != getattr(repo, k) for k in
                                  ('repo_id', 'path', 'exchange', 'archive', 'commit', 'fingerprint', 'error')):
            raise ValueError('repository context changed during artifact observation')
    except ERRORS as exc:
        result['errors'].append(str(exc))
        result['stale'] = True
    if candidates and not result['incomplete'] and not result['errors']:
        result['selected_candidate'] = str(_select_exchange_candidate(candidates).path)
    rows = result['artifacts']
    for patch in (r for r in rows if r['kind'] == 'patch_package' and not r['error']):
        patch['source_candidates'] = sorted({r['sha256'] for r in rows if r.get('context') == patch['expected'] and not r['error']})
        patch['result_links'] = sorted({r['sha256'] for r in rows if r.get('patch_sha256') == patch['sha256']
                                 and r.get('expected') == patch['expected'] and not r['error']})
        patch['source_relation'] = 'matching states only; source ZIP not uniquely recorded'
    runs = {}
    for row in rows:
        if row.get('run_id') and not row.get('error'):
            runs.setdefault(row['run_id'], set()).add(row['sha256'])
    for row in rows:
        row['ambiguous_run'] = len(runs.get(row.get('run_id'), ())) > 1
        if row.get('attempt_run_id'):
            row['attempt_result_missing'] = not any(r.get('run_id') == row['attempt_run_id']
                and r.get('patch_sha256') == row['sha256'] and r.get('expected') == row['expected']
                and not r['error'] for r in rows)
    return result
