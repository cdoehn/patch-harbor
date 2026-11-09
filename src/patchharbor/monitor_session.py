"""Selection and filtering are private to each viewer instance."""
from __future__ import annotations

from dataclasses import dataclass, field

VIEWS = ('overview', 'exchanges', 'bundles', 'history', 'logs')


@dataclass
class MonitorSession:
    view: str = 'overview'
    match: str = ''
    artifact_match: str = ''
    include_archive: bool = False
    focus: str = 'repositories'
    repository_id: str | None = None
    selections: dict[str, str] = field(default_factory=dict)
    offsets: dict[str, int] = field(default_factory=dict)
    descending: bool = False

    def repositories(self, document):
        return sorted((r for r in document.get('repositories', [])
                       if self.match.casefold() in (r['path'] + ' ' + r['repo_id']).casefold()),
                      key=lambda r: (r['name'].casefold(), r['repo_id']), reverse=self.descending)

    def selected(self, document):
        rows = self.repositories(document)
        selected = next((r for r in rows if r['repo_id'] == self.repository_id), rows[0] if rows else None)
        if selected is not None:
            self.repository_id = selected['repo_id']
        return selected

    def move(self, document, delta):
        if self.focus == 'details' and self.view in ('bundles', 'history'):
            rows = self.artifacts(document)
            selected = self.selected_artifact(document)
            if selected:
                index = max(0, min(len(rows) - 1, rows.index(selected) + delta))
                self.selections[str(self.repository_id)] = artifact_key(rows[index])
            return
        if self.focus == 'details':
            self.offsets[self.view] = max(0, self.offsets.get(self.view, 0) + delta)
            return
        rows = self.repositories(document)
        selected = self.selected(document)
        if selected:
            index = rows.index(selected)
            self.repository_id = rows[max(0, min(len(rows) - 1, index + delta))]['repo_id']

    def artifacts(self, document):
        rows = document.get('bundle_view', {}).get('artifacts', [])
        return sorted((r for r in rows if self.artifact_match.casefold() in
                       ' '.join(str(r.get(k) or '') for k in ('name', 'sha256', 'repo_id', 'run_id')).casefold()
                       and (self.view != 'logs' or r['kind'] == 'result_bundle')
                       and (self.view != 'history' or (r.get('repo_id') == self.repository_id
                            and (r.get('run_id') or r.get('attempt_result_missing'))))),
                      key=lambda r: (r.get('mtime_ns', 0), r['path']), reverse=not self.descending)

    def selected_artifact(self, document):
        rows = self.artifacts(document)
        key = str(self.repository_id)
        row = next((r for r in rows if artifact_key(r) == self.selections.get(key)), rows[0] if rows else None)
        if row:
            self.selections[key] = artifact_key(row)
        return row


def artifact_key(row):
    return row['path'] + ':' + (row.get('sha256') or 'unknown')


def result_semantic(row):
    if row.get('stale'):
        return 'unknown'
    if row.get('error') or row.get('result_status') == 'failed':
        return 'dirty'
    primary = row.get('primary_result')
    if primary:
        return 'clean' if primary.get('success') is True else 'dirty'
    if row.get('replay_status') == 'failed':
        return 'dirty'
    return 'unknown'


def git_semantic(row):
    if row.get('stale') or row.get('error') or row.get('registration') != 'ok':
        return 'unknown'
    return row.get('git_status', 'unknown')
