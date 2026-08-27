from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).parents[1]
CORE_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor"
WATCHER_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor_watcher"
PACKAGE_ROOTS = {
    "patchharbor": CORE_PACKAGE_ROOT,
    "patchharbor_watcher": WATCHER_PACKAGE_ROOT,
}

ENTRYPOINT_MODULES = {
    "patchharbor.cli",
    "patchharbor_watcher",
    "patchharbor_watcher.cli",
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


def _project_imports(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        names: tuple[str, ...] = ()
        if isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        elif isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        imports.update(
            name
            for name in names
            if name == "patchharbor"
            or name.startswith("patchharbor.")
            or name == "patchharbor_watcher"
            or name.startswith("patchharbor_watcher.")
        )
    return frozenset(imports)


def _import_roots(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return frozenset(roots)


def _dependency_graph() -> dict[str, frozenset[str]]:
    modules = _runtime_modules()
    names = frozenset(modules)
    return {
        module: frozenset(
            dependency
            for dependency in _project_imports(path)
            if dependency in names
        )
        for module, path in modules.items()
    }


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


def _assert_acyclic(graph: dict[str, frozenset[str]]) -> None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            cycle = visiting[visiting.index(module) :] + [module]
            raise AssertionError("cyclic runtime import: " + " -> ".join(cycle))
        if module in visited:
            return
        visiting.append(module)
        for dependency in sorted(graph[module]):
            visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in sorted(graph):
        visit(module)


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


def test_application_is_the_only_core_workflow_orchestrator() -> None:
    graph = _dependency_graph()
    workflow_boundaries = {
        "patchharbor.registration",
        "patchharbor.repository_state",
        "patchharbor.result_bundle",
        "patchharbor.apply_mutation",
        "patchharbor.sources",
        "patchharbor.bundles",
        "patchharbor.execution",
        "patchharbor.exchange",
        "patchharbor.presentation",
    }
    application_dependencies = graph["patchharbor.application"]
    assert workflow_boundaries <= application_dependencies

    multi_workflow_modules = {
        module
        for module, dependencies in graph.items()
        if module.startswith("patchharbor.")
        and len(dependencies & workflow_boundaries) >= 3
    }
    assert multi_workflow_modules == {"patchharbor.application"}

    application_users = {
        module
        for module, dependencies in graph.items()
        if "patchharbor.application" in dependencies
    }
    assert application_users == {"patchharbor.cli"}


def test_cli_composes_public_boundaries_without_domain_orchestration() -> None:
    dependencies = _dependency_graph()["patchharbor.cli"]
    assert "patchharbor.application" in dependencies
    forbidden = {
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
    assert not _forbidden_dependencies(dependencies, forbidden)


def test_runtime_responsibilities_follow_the_specified_boundaries() -> None:
    graph = _dependency_graph()
    forbidden_by_module = {
        "patchharbor.exchange": {
            "patchharbor.application",
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
            "patchharbor.application",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.git_*",
            "patchharbor.parser",
            "patchharbor.presentation",
            "patchharbor.repository*",
            "patchharbor.result_bundle*",
        },
        "patchharbor.bundles": {
            "patchharbor.application",
            "patchharbor.execution",
            "patchharbor.payload_files",
            "patchharbor.presentation",
            "patchharbor.registry",
            "patchharbor.repository*",
            "patchharbor.sources",
        },
        "patchharbor.payload_files": {
            "patchharbor.application",
            "patchharbor.execution",
            "patchharbor.presentation",
            "patchharbor.registry",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.patch_manifest": {
            "patchharbor.application",
            "patchharbor.execution",
            "patchharbor.git_*",
            "patchharbor.presentation",
            "patchharbor.repository*",
            "patchharbor.result_bundle*",
        },
        "patchharbor.registry": {
            "patchharbor.application",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.repository_state": {
            "patchharbor.application",
            "patchharbor.execution",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.result_bundle*",
            "patchharbor_watcher*",
        },
        "patchharbor.locks": {
            "patchharbor.application",
            "patchharbor.bundles",
            "patchharbor.execution",
            "patchharbor.patch_manifest",
            "patchharbor.patch_package",
            "patchharbor.presentation",
            "patchharbor.repository_state",
            "patchharbor.result_bundle*",
        },
        "patchharbor.execution": {
            "patchharbor.application",
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
    assert graph["patchharbor.presentation"] == frozenset()

    for module, forbidden in forbidden_by_module.items():
        violations = _forbidden_dependencies(graph[module], forbidden)
        assert not violations, f"{module} imports {sorted(violations)}"

    for module, dependencies in graph.items():
        if not module.startswith("patchharbor.result_bundle"):
            continue
        violations = _forbidden_dependencies(
            dependencies,
            {
                "patchharbor.application",
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
        if module.startswith("patchharbor.platform"):
            continue
        assert _import_roots(path).isdisjoint(platform_only_roots), module

    graph = _dependency_graph()
    execution_dependencies = graph["patchharbor.execution"]
    assert "patchharbor.platform" in execution_dependencies
    assert "patchharbor.platform.posix" not in execution_dependencies
    assert "patchharbor.platform.windows" not in execution_dependencies
    assert "patchharbor.platform.runtime" in graph["patchharbor.interpreters"]
    assert "patchharbor.platform.filesystem" in graph["patchharbor.payload_files"]
    assert "patchharbor.platform.filesystem" in graph["patchharbor.git_capture"]
    assert "patchharbor.platform.locking" in graph["patchharbor.locks"]
    assert "patchharbor.platform.paths" in graph["patchharbor.path_configuration"]
    assert "patchharbor.platform.runtime" in graph["patchharbor.user_paths"]
    assert "patchharbor.physical_paths" not in graph

    git_capture_source = modules["patchharbor.git_capture"].read_text(
        encoding="utf-8"
    )
    for platform_detail in (
        "os.name",
        "isjunction",
        "is_junction",
        "st_birthtime_ns",
    ):
        assert platform_detail not in git_capture_source


def test_watcher_is_separate_and_uses_only_the_public_apply_process_boundary() -> None:
    graph = _dependency_graph()
    core_modules = {
        module for module in graph if module.startswith("patchharbor.")
    }
    watcher_modules = {
        module for module in graph if module.startswith("patchharbor_watcher.")
    }

    for module in core_modules:
        assert not any(
            dependency.startswith("patchharbor_watcher")
            for dependency in graph[module]
        )

    allowed_shared_core_boundaries = {
        "patchharbor.path_configuration",
        "patchharbor.platform.paths",
        "patchharbor.platform.filesystem",
        "patchharbor.user_paths",
    }
    for module in watcher_modules:
        core_dependencies = {
            dependency
            for dependency in graph[module]
            if dependency.startswith("patchharbor.")
        }
        assert core_dependencies <= allowed_shared_core_boundaries, module

    assert not {
        dependency
        for dependency in graph["patchharbor_watcher.apply_boundary"]
        if dependency.startswith("patchharbor.")
    }

    for module in watcher_modules:
        path = _runtime_modules()[module]
        assert _import_roots(path).isdisjoint(
            FORBIDDEN_ASYNC_OR_TRANSPORT_ROOTS
        ), module
        if module != "patchharbor_watcher.apply_boundary":
            assert "subprocess" not in _import_roots(path), module

    assert not (PROJECT_ROOT / "src" / "repo_assist").exists()
    assert not (PROJECT_ROOT / "src" / "promptbridge").exists()


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
