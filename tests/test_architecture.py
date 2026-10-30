from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
import sys

from tests.architecture_support import (
    assert_acyclic as _assert_acyclic, import_names, is_cli, is_workflow, workflow_violations,
)


PROJECT_ROOT = Path(__file__).parents[1]
CORE_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor"
WATCHER_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor_watcher"
PACKAGE_ROOTS = {
    "patchharbor": CORE_PACKAGE_ROOT,
    "patchharbor_watcher": WATCHER_PACKAGE_ROOT,
}

ENTRYPOINT_MODULES = {
    # PP-04A stages a data-only build profile, consumed by the PP-04B provider.
    "patchharbor.cli",
    "patchharbor_watcher",
    "patchharbor_watcher.cli",
    "patchharbor_watcher.worker",
}
FORBIDDEN_SCOPE_MODULE_PARTS = {
    "clipboard",
    "common",
    "helpers",
    "plugin",
    "plugins",
    "promptbridge",
    "repo_assist",
    "save_mode",
    "ssh",
    "test_manager",
    "testmanager",
    "utils",
    "websocket",
    "websockets",
}
FORBIDDEN_ASYNC_OR_TRANSPORT_ROOTS = {
    "asyncio",
    "http",
    "requests",
    "socket",
    "ssl",
    "urllib",
    "websockets",
}


def _module_name(package: str, root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    if relative.name == "__init__.py":
        suffix = relative.parent.parts
    else:
        suffix = relative.with_suffix("").parts
    return ".".join((package, *suffix)) if suffix else package


def _runtime_modules() -> dict[str, Path]:
    return {
        _module_name(package, root, path): path
        for package, root in PACKAGE_ROOTS.items()
        for path in root.rglob("*.py")
    }


def _project_imports(path: Path, modules=None) -> frozenset[str]:
    modules = _runtime_modules() if modules is None else modules
    module = next(name for name, candidate in modules.items() if candidate == path)
    imports = import_names(path.read_text(encoding="utf-8"), module, set(modules),
                           is_package=path.name == "__init__.py")
    return frozenset(name for name in imports
                     if name == "patchharbor" or name.startswith("patchharbor.")
                     or name == "patchharbor_watcher" or name.startswith("patchharbor_watcher."))


def _import_roots(path: Path) -> frozenset[str]:
    modules = _runtime_modules()
    module = next(name for name, candidate in modules.items() if candidate == path)
    names = import_names(path.read_text(encoding="utf-8"), module, set(modules),
                         is_package=path.name == "__init__.py")
    return frozenset(name.split(".", 1)[0] for name in names)


def _dependency_graph() -> dict[str, frozenset[str]]:
    modules = _runtime_modules()
    return {name: _project_imports(path, modules) & modules.keys() for name, path in modules.items()}


def _matches(dependency: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        return dependency.startswith(pattern[:-1])
    return dependency == pattern or dependency.startswith(pattern + ".")


def _forbidden_dependencies(
    dependencies: Iterable[str],
    patterns: Iterable[str],
) -> set[str]:
    return {
        dependency
        for dependency in dependencies
        if any(_matches(dependency, pattern) for pattern in patterns)
    }




def test_runtime_import_graph_is_acyclic() -> None:
    _assert_acyclic(_dependency_graph())


def test_runtime_has_no_dead_or_generic_scope_modules() -> None:
    graph = _dependency_graph()
    inbound: dict[str, set[str]] = {module: set() for module in graph}
    for module, dependencies in graph.items():
        for dependency in dependencies:
            inbound[dependency].add(module)

    assert {module for module, users in inbound.items() if not users} == (
        ENTRYPOINT_MODULES
    )
    for module in graph:
        assert set(module.split(".")).isdisjoint(
            FORBIDDEN_SCOPE_MODULE_PARTS
        ), module


def test_runtime_has_no_async_core_or_transport_framework() -> None:
    async_nodes = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.Await,
    )
    for module, path in _runtime_modules().items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(isinstance(node, async_nodes) for node in ast.walk(tree)), (
            module
        )
        assert _import_roots(path).isdisjoint(
            FORBIDDEN_ASYNC_OR_TRANSPORT_ROOTS
        ), module


def test_application_layer_can_share_workflows_without_reverse_dependencies() -> None:
    graph = _dependency_graph()
    assert any(is_workflow(name) for name in graph["patchharbor.api"])
    assert not workflow_violations(graph)


def test_cli_composes_public_boundaries_without_domain_orchestration() -> None:
    graph = _dependency_graph()
    cli_modules = {name: deps for name, deps in graph.items() if is_cli(name)}
    assert any("patchharbor.api" in deps for deps in cli_modules.values())
    forbidden = {
        "patchharbor.application*",
        "patchharbor.output",
        "patchharbor.progress",
        "patchharbor.apply_mutation",
        "patchharbor.apply_preflight",
        "patchharbor.apply_repository",
        "patchharbor.bundles",
        "patchharbor.exchange",
        "patchharbor.git_*",
        "patchharbor.locks",
        "patchharbor.patch_manifest",
        "patchharbor.patch_package",
        "patchharbor.payload_files",
        "patchharbor.registration",
        "patchharbor.registry",
        "patchharbor.repository*",
        "patchharbor.result_bundle*",
        "patchharbor.sources",
    }
    for module, dependencies in cli_modules.items():
        assert not _forbidden_dependencies(dependencies, forbidden), module


def test_runtime_responsibilities_follow_the_specified_boundaries() -> None:
    graph = _dependency_graph()
    forbidden_by_module = {
        "patchharbor.exchange": {
            "patchharbor.application*",
            "patchharbor.apply_*",
            "patchharbor.execution",
            "patchharbor.git_*",
            "patchharbor.locks",
            "patchharbor.presentation",
            "patchharbor.registration",
            "patchharbor.registry",
            "patchharbor.repository*",
            "patchharbor.result_bundle*",
            "patchharbor_watcher*",
        },
        "patchharbor.sources": {
            "patchharbor.application*",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.git_*",
            "patchharbor.parser",
            "patchharbor.presentation",
            "patchharbor.repository*",
            "patchharbor.result_bundle*",
        },
        "patchharbor.bundles": {
            "patchharbor.application*",
            "patchharbor.execution",
            "patchharbor.payload_files",
            "patchharbor.presentation",
            "patchharbor.registry",
            "patchharbor.repository*",
            "patchharbor.sources",
        },
        "patchharbor.payload_files": {
            "patchharbor.application*",
            "patchharbor.execution",
            "patchharbor.presentation",
            "patchharbor.registry",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.patch_manifest": {
            "patchharbor.application*",
            "patchharbor.execution",
            "patchharbor.git_*",
            "patchharbor.presentation",
            "patchharbor.repository*",
            "patchharbor.result_bundle*",
        },
        "patchharbor.registry": {
            "patchharbor.application*",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.repository_state": {
            "patchharbor.application*",
            "patchharbor.execution",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.result_bundle*",
            "patchharbor_watcher*",
        },
        "patchharbor.locks": {
            "patchharbor.application*",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.patch_manifest",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.execution": {
            "patchharbor.application*",
            "patchharbor.git_*",
            "patchharbor.patch_manifest",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.registry",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
            "patchharbor_watcher*",
        },
    }

    assert graph["patchharbor.parser"] == frozenset()
    assert graph["patchharbor.identifier_presentation"] == frozenset()
    assert graph["patchharbor.presentation"] <= {
        "patchharbor.errors", "patchharbor.identifier_presentation",
        "patchharbor.models", "patchharbor.progress",
    }
    assert graph["patchharbor.progress"] <= {"patchharbor.models"}

    for module, forbidden in forbidden_by_module.items():
        violations = _forbidden_dependencies(graph[module], forbidden)
        assert not violations, f"{module} imports {sorted(violations)}"

    for module, dependencies in graph.items():
        if not module.startswith("patchharbor.result_bundle"):
            continue
        violations = _forbidden_dependencies(
            dependencies,
            {
                "patchharbor.application*",
                "patchharbor.apply_mutation",
                "patchharbor.apply_preflight",
                "patchharbor.execution",
                "patchharbor.presentation",
                "patchharbor_watcher*",
            },
        )
        assert not violations, f"{module} imports {sorted(violations)}"


def test_platform_specific_mechanics_stay_inside_platform_package() -> None:
    modules = _runtime_modules()
    platform_only_roots = {"ctypes", "fcntl", "msvcrt"}
    for module, path in modules.items():
        if module.startswith(("patchharbor.platform.", "patchharbor_watcher.platform.")):
            continue
        if module in {"patchharbor.platform", "patchharbor_watcher.platform"}:
            continue
        assert _import_roots(path).isdisjoint(platform_only_roots), module
    graph = _dependency_graph()
    assert not graph["patchharbor.execution"] & {
        "patchharbor.platform.posix", "patchharbor.platform.windows"}
    assert not graph["patchharbor_watcher.events"]
    for module, dependencies in graph.items():
        if module == "patchharbor_watcher.platform" or module.startswith("patchharbor_watcher.platform."):
            assert all(name == "patchharbor_watcher.events" or name.startswith("patchharbor_watcher.platform.")
                       for name in dependencies), module


def test_watcher_uses_public_api_with_an_isolated_worker_boundary() -> None:
    graph = _dependency_graph()
    allowed = {"patchharbor", "patchharbor.api", "patchharbor.platform.paths", "patchharbor.platform.filesystem"}
    for module, dependencies in graph.items():
        if module == "patchharbor" or module.startswith("patchharbor."):
            assert not any(name == "patchharbor_watcher" or name.startswith("patchharbor_watcher.")
                           for name in dependencies), module
        else:
            core = {name for name in dependencies if name == "patchharbor" or name.startswith("patchharbor.")}
            assert core <= allowed, module
            if module == "patchharbor_watcher.apply_boundary":
                assert not core
            else:
                assert "subprocess" not in _import_roots(_runtime_modules()[module]), module
    assert "patchharbor.api" in graph["patchharbor_watcher.worker"]
    assert graph["patchharbor_watcher.worker"] <= {"patchharbor.api", "patchharbor_watcher.protocol"}


def test_runtime_imports_only_standard_library_and_project_packages() -> None:
    imported_roots: set[str] = set()
    for path in _runtime_modules().values():
        imported_roots.update(_import_roots(path))

    allowed = set(sys.stdlib_module_names) | {
        "__future__",
        "patchharbor",
        "patchharbor_watcher",
    }
    assert imported_roots <= allowed


def test_bundle_handoff_is_passive_output_not_chat_or_commit_orchestration() -> None:
    graph = _dependency_graph()
    for module in (
        "patchharbor.bundle_handoff",
        "patchharbor.chat_instructions",
        "patchharbor.result_bundle_handoff",
        "patchharbor.platform.environment",
    ):
        assert not _forbidden_dependencies(graph[module], {
            "patchharbor.application*", "patchharbor.execution", "patchharbor.apply_*",
            "patchharbor.git_*", "patchharbor.registry", "patchharbor_watcher*",
        })
    assert "patchharbor.chat_instructions" not in graph["patchharbor.patch_package"]
    for module in ("patchharbor.chat_instructions", "patchharbor.bundle_handoff"):
        assert "subprocess" not in _import_roots(_runtime_modules()[module])


def test_archive_proofs_and_files_do_not_import_execution_or_cli() -> None:
    modules = _runtime_modules()
    prohibited = {"patchharbor.application*", "patchharbor.cli*",
                  "patchharbor.execution", "patchharbor.presentation"}
    for name in ("archive_policy", "archive_evidence", "archive_git",
                 "archive_files", "exchange_archive", "platform.archive"):
        dependencies = _project_imports(modules["patchharbor." + name])
        assert not _forbidden_dependencies(dependencies, prohibited)
    assert not _project_imports(modules["patchharbor.archive_policy"])
    assert "patchharbor.git_commands" not in _project_imports(
        modules["patchharbor.archive_files"]
    )
    assert "patchharbor.platform.archive" not in _project_imports(
        modules["patchharbor.archive_evidence"]
    )


def test_domain_errors_and_application_do_not_depend_on_cli_statuses() -> None:
    modules = _runtime_modules()
    graph = _dependency_graph()
    for module in ({name for name in graph if is_workflow(name)} | {
        "patchharbor.errors", "patchharbor.execution", "patchharbor.apply_mutation", "patchharbor.sources"}):
        assert not _forbidden_dependencies(graph[module], {"patchharbor.exit_status", "patchharbor.cli*"})
        tree = ast.parse(modules[module].read_text(encoding="utf-8"))
        assert not any(isinstance(n, ast.Attribute) and n.attr == "process_exit_code"
                       for n in ast.walk(tree))
    assert any("patchharbor.exit_status" in deps for name, deps in graph.items() if is_cli(name))
    assert "patchharbor.exit_status" in graph["patchharbor.run_report"]


def test_public_api_does_not_invoke_cli_or_duplicate_core_workflows() -> None:
    graph = _dependency_graph()
    dependencies = graph["patchharbor.api"]
    assert any(is_workflow(name) for name in dependencies)
    assert not _forbidden_dependencies(dependencies, {
        "patchharbor.cli*", "patchharbor.presentation", "patchharbor.exchange*",
        "patchharbor.apply_*", "patchharbor.git_*", "patchharbor.registry",
        "patchharbor_watcher*",
    })
    assert "subprocess" not in _import_roots(_runtime_modules()["patchharbor.api"])


def test_current_pyz_and_shared_profiles_do_not_depend_on_legacy_readers() -> None:
    graph = _dependency_graph()
    forbidden = {"patchharbor.runtime_wheel", "patchharbor.result_runtime"}
    for module in ("patchharbor.runtime_pyz", "patchharbor.result_pyz",
                   "patchharbor.runtime_profile", "patchharbor.result_runtime_metadata",
                   "patchharbor.runtime_sources",
                   "patchharbor.pyz_artifact", "patchharbor.result_resources"):
        pending, seen = [module], set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(graph.get(current, ()))
        assert not seen & forbidden, (module, seen & forbidden)
