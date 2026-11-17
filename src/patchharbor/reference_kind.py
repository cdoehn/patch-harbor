"""State and Result share a snapshot schema, never execution semantics."""
from __future__ import annotations

from enum import Enum


class ReferenceBundleKind(str, Enum):
    STATE = 'state'
    RESULT = 'result'

    @property
    def label(self) -> str:
        return self.value.title()

    @property
    def marker(self) -> str:
        return 'patch-harbor-' + self.value + '-bundle'

    @property
    def artifact_kind(self) -> str:
        return self.value + '_bundle'


def kind_for_operation(operation: str) -> ReferenceBundleKind:
    if operation == 'bundle':
        return ReferenceBundleKind.STATE
    if operation == 'execute':
        return ReferenceBundleKind.RESULT
    raise ValueError('unsupported reference operation')


def kind_for_marker(marker: object) -> ReferenceBundleKind | None:
    if type(marker) is not str:
        return None
    return next((kind for kind in ReferenceBundleKind if kind.marker == marker), None)
