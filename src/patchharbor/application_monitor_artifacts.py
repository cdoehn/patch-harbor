"""Read-only Exchange facts; never execute, recover, lock or archive a package."""
from __future__ import annotations

from pathlib import Path

from patchharbor.application_monitor import monitor_snapshot
from patchharbor.application_exchange import _select_exchange_candidate
from patchharbor.errors import PatchHarborError
from patchharbor.exchange import classify_exchange_artifact
from patchharbor.exchange_state import ExchangeFileIdentity, ExchangeStateSnapshot, _parse_state
from patchharbor.models import RepositoryId, GitObjectId, GitObjectFormat
from patchharbor.monitor_types import observed_at
from patchharbor.platform.filesystem import PathKind, path_kind, read_stable_regular_file_bounded
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.result_reader import capture_result_payloads, ReferenceContext
from patchharbor.user_paths import registration_user_paths

POLICY = ResourcePolicy(max_input_artifact_bytes=64*1024*1024,
                        max_content_bytes=64*1024*1024, max_zip_total_bytes=128*1024*1024)
ERRORS = (PatchHarborError, OSError, ValueError, RuntimeError)


def binding(value):
    if value is None:
        return None
    return {name: str(getattr(value, name)) for name in
            ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')}


def replay_snapshot():
    paths = registration_user_paths(create_configuration_directory=False, create_lock_directory=False)
    path = paths.exchange_state_path
    content = read_stable_regular_file_bounded(path, max_bytes=4*1024*1024).content if path.exists() else None
    return _parse_state(content) if content is not None else ExchangeStateSnapshot()


def artifact_fact(path, archived, state):
    row = {'path': str(path), 'name': path.name, 'archived': archived, 'kind': 'unknown',
           'sha256': None, 'repo_id': None, 'error': None}
    try:
        if path_kind(path) is not PathKind.REGULAR_FILE:
            raise ValueError('not a regular file; not followed')
        if path.stat().st_size > POLICY.max_input_artifact_bytes:
            raise ValueError('artifact exceeds the 64 MiB observation limit')
        artifact = classify_exchange_artifact(path, resource_policy=POLICY)
        row.update(sha256=artifact.identity.sha256, kind=artifact.kind.value,
                   mtime_ns=artifact.mtime_ns, size=path.stat().st_size)
        if artifact.selection is not None:
            expected = binding(artifact.selection)
            record = state.record_for(artifact.identity)
            row.update(repo_id=expected['repo_id'], expected=expected,
                       replay_status=record.apply_status.value if record and record.apply_status else None,
                       attempt_run_id=record.attempt_run_id if record else None,
                       result_sha256=record.result_sha256 if record else None,
                       completed_commit=str(record.completed_commit) if record and record.completed_commit else None)
        elif artifact.kind.value == 'result_bundle':
            captured = capture_result_payloads(path, resource_policy=POLICY, expected_identity=path.lstat())
            if captured.sha256 != artifact.identity.sha256:
                raise ValueError('artifact changed during observation')
            facts = captured.facts
            row.update(repo_id=str(facts.context.repo_id), context=binding(facts.context),
                       expected=binding(facts.expected), run_id=facts.run_id, operation=facts.operation,
                       dry_run=facts.dry_run, primary_result=facts.primary_result.as_document(),
                       result_status='created', patch_sha256=facts.patch_sha256,
                       completed_commit=str(facts.completed_commit) if facts.completed_commit else None)
        return row, artifact
    except ERRORS as exc:
        row['error'] = str(exc)
        return row, None


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
    context = None
    if repo.commit is not None and repo.error is None:
        context = ReferenceContext(RepositoryId(repo.repo_id), repo.path,
                                  GitObjectId(repo.commit, GitObjectFormat.for_hex_length(len(repo.commit))),
                                  repo.git_status == 'dirty', repo.fingerprint, 'patchharbor-state-v1')
    for parent, archived in directories:
        try:
            paths = sorted(parent.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            result['errors'].append(str(exc))
            continue
        for path in paths:
            if path_kind(path) is PathKind.DIRECTORY:
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
            row, artifact = artifact_fact(path, archived, state)
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
                row['manual_retry_possible'] = row['replay_status'] == 'failed'
            result['artifacts'].append(row)
    if candidates and not result['incomplete'] and not result['errors']:
        result['selected_candidate'] = str(_select_exchange_candidate(candidates).path)
    rows = result['artifacts']
    for patch in (r for r in rows if r['kind'] == 'patch_package' and not r['error']):
        patch['source_candidates'] = [r['sha256'] for r in rows if r.get('context') == patch['expected'] and not r['error']]
        patch['result_links'] = [r['sha256'] for r in rows if r.get('patch_sha256') == patch['sha256']
                                 and r.get('expected') == patch['expected'] and not r['error']]
        patch['source_relation'] = 'matching states only; source ZIP not uniquely recorded'
    return result


def monitor_log(path, expected_sha256):
    if path_kind(path) is not PathKind.REGULAR_FILE:
        raise ValueError('log source must be a regular Result file')
    captured = capture_result_payloads(path, resource_policy=POLICY, expected_identity=path.lstat())
    if captured.sha256 != expected_sha256:
        raise ValueError('selected Result identity changed; refresh the artifact list')
    logs = {p.relative_path: p.content for p in captured.payloads if p.relative_path in ('logs/execution.log', 'logs/run.json')}
    content = logs.get('logs/execution.log', logs.get('logs/run.json', b''))
    tail = content[-64*1024:]
    return {'sha256': captured.sha256, 'run_id': captured.facts.run_id,
            'truncated': len(tail) < len(content), 'text': tail.decode('utf-8', errors='replace'),
            'observed_at': observed_at()}
