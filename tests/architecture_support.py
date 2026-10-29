"""Static import and layer checks; project source is parsed, never executed."""
from __future__ import annotations

import ast
from importlib.util import resolve_name


def import_names(source: str, module: str, known: set[str], *, is_package: bool = False) -> frozenset[str]:
    """Resolve aliases and relative imports against the actual module inventory.

    ``from package import child`` depends on child when it is a real module;
    ordinary symbol imports depend on their defining module. Implicit package
    initialization is not a separate edge (it would invent initializer cycles).
    """
    imports = set()
    package = module if is_package else module.rpartition('.')[0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (resolve_name('.' * node.level + (node.module or ''), package)
                    if node.level else node.module)
            if not base:
                raise ValueError('import has no resolvable module')
            for alias in node.names:
                child = base + '.' + alias.name
                imports.add(child if child in known else base)
    return frozenset(imports)


def assert_acyclic(graph: dict[str, frozenset[str]]) -> None:
    visiting = []
    visited = set()
    def visit(module):
        if module in visiting:
            raise AssertionError('cyclic runtime import: ' + ' -> '.join(visiting + [module]))
        if module in visited:
            return
        visiting.append(module)
        for dependency in sorted(graph.get(module, ())):
            visit(dependency)
        visiting.pop()
        visited.add(module)
    for module in sorted(graph):
        visit(module)


def is_workflow(module: str) -> bool:
    return module == 'patchharbor.application' or module.startswith('patchharbor.application_')


def is_cli(module: str) -> bool:
    return module == 'patchharbor.cli' or module.startswith('patchharbor.cli_')


WORKFLOW_BOUNDARIES = frozenset({
    'patchharbor.registration', 'patchharbor.repository_state', 'patchharbor.result_bundle',
    'patchharbor.apply_mutation', 'patchharbor.sources', 'patchharbor.bundles',
    'patchharbor.execution', 'patchharbor.exchange',
})
WORKFLOW_FORBIDDEN = frozenset({
    'patchharbor.presentation', 'patchharbor.identifier_presentation', 'patchharbor.exit_status',
})


def workflow_violations(graph: dict[str, frozenset[str]]) -> set[tuple[str, str]]:
    """Permit a split application layer while keeping consumers below the facade.

    API -> application/application_* -> domain services. Workflow helpers may
    use each other without cycles. Domain services cannot call back into them;
    CLI helpers cannot bypass the API. Presentation/status conversion stays out
    of workflows. Combining three service boundaries outside that layer remains
    a duplicate orchestrator, as in the original architecture constraint.
    """
    violations = set()
    for module, dependencies in graph.items():
        for dependency in dependencies:
            if is_workflow(dependency) and not (is_workflow(module) or module == 'patchharbor.api'):
                violations.add((module, dependency))
            if is_workflow(module) and (is_cli(dependency) or dependency in WORKFLOW_FORBIDDEN):
                violations.add((module, dependency))
        if module.startswith('patchharbor.') and not is_workflow(module):
            services = dependencies & WORKFLOW_BOUNDARIES
            if len(services) >= 3:
                violations.update((module, service) for service in services)
    return violations
