"""Adversarial import examples keep the architecture gate independent of spelling."""
from __future__ import annotations

import pytest

from tests.architecture_support import assert_acyclic, import_names, workflow_violations


KNOWN = {'patchharbor', 'patchharbor.api', 'patchharbor.application',
         'patchharbor.application_exchange', 'patchharbor.result_reader',
         'patchharbor.platform', 'patchharbor.platform.filesystem'}


@pytest.mark.parametrize('source,module,expected', [
    ('import patchharbor.application as flow', 'patchharbor.api', {'patchharbor.application'}),
    ('from patchharbor import application as flow', 'patchharbor.api', {'patchharbor.application'}),
    ('from . import application as flow', 'patchharbor.api', {'patchharbor.application'}),
    ('from .application import run_bundle', 'patchharbor.api', {'patchharbor.application'}),
    ('from .. import result_reader', 'patchharbor.platform.filesystem', {'patchharbor.result_reader'}),
    ('from .platform import filesystem as fs', 'patchharbor.api', {'patchharbor.platform.filesystem'}),
    ('from patchharbor import __version__, api', 'patchharbor.application', {'patchharbor', 'patchharbor.api'}),
    ('def deferred():\n    from . import application_exchange', 'patchharbor.api', {'patchharbor.application_exchange'}),
    ('# import forbidden\ntext="import imaginary"\nraise RuntimeError("must never execute")', 'patchharbor.api', set()),
])
def test_import_edges_resolve_real_modules_without_executing_source(source, module, expected):
    assert import_names(source, module, KNOWN) == expected


def test_package_relative_import_resolves_from_initializer():
    assert import_names('from . import filesystem', 'patchharbor.platform', KNOWN,
                        is_package=True) == {'patchharbor.platform.filesystem'}


@pytest.mark.parametrize('module', ['patchharbor.application', 'patchharbor.application_exchange',
                                  'patchharbor.application_configuration'])
def test_workflow_can_be_split_without_moving_into_cli_or_domain(module):
    services = frozenset({'patchharbor.registration', 'patchharbor.repository_state',
                          'patchharbor.result_bundle', 'patchharbor.exchange'})
    graph = {'patchharbor.api': frozenset({module}), module: services}
    assert workflow_violations(graph) == set()
    assert_acyclic(graph)


@pytest.mark.parametrize('caller,dependency', [
    ('patchharbor.cli', 'patchharbor.application'),
    ('patchharbor.cli_dispatch', 'patchharbor.application_exchange'),
    ('patchharbor.result_reader', 'patchharbor.application_configuration'),
    ('patchharbor.application_exchange', 'patchharbor.cli_dispatch'),
    ('patchharbor.application', 'patchharbor.presentation'),
    ('patchharbor.application_configuration', 'patchharbor.exit_status'),
])
def test_workflow_layer_rejects_reverse_and_presentation_dependencies(caller, dependency):
    assert workflow_violations({caller: frozenset({dependency})}) == {(caller, dependency)}


def test_orchestration_cannot_hide_in_a_domain_service():
    services = frozenset({'patchharbor.registration', 'patchharbor.exchange', 'patchharbor.execution'})
    assert workflow_violations({'patchharbor.patch_manifest': services}) == {
        ('patchharbor.patch_manifest', service) for service in services}


@pytest.mark.parametrize('source', ['from . import application_exchange as hidden',
                                  'import patchharbor.application_exchange as hidden'])
def test_aliases_cannot_hide_a_cycle_in_split_workflows(source):
    forward = import_names(source, 'patchharbor.application', KNOWN)
    reverse = import_names('from . import application', 'patchharbor.application_exchange', KNOWN)
    with pytest.raises(AssertionError):
        assert_acyclic({'patchharbor.application': forward, 'patchharbor.application_exchange': reverse})
