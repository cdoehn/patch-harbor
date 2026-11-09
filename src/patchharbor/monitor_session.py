"""Selection and filtering are private to each viewer instance."""
from __future__ import annotations

from dataclasses import dataclass, field

VIEWS = ('overview', 'exchanges')


@dataclass
class MonitorSession:
    view: str = 'overview'
    match: str = ''
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
        rows = self.repositories(document)
        selected = self.selected(document)
        if selected:
            index = rows.index(selected)
            self.repository_id = rows[max(0, min(len(rows) - 1, index + delta))]['repo_id']


def git_semantic(row):
    if row.get('stale') or row.get('error') or row.get('registration') != 'ok':
        return 'unknown'
    return row.get('git_status', 'unknown')
