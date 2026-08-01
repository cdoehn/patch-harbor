from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "patchharbor"


def _local_imports(module_name: str) -> set[str]:
    tree = ast.parse(
        (PACKAGE_ROOT / f"{module_name}.py").read_text(encoding="utf-8")
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("patchharbor."):
                imports.add(node.module.split(".", 1)[1].split(".", 1)[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("patchharbor."):
                    imports.add(alias.name.split(".", 1)[1].split(".", 1)[0])
    return imports


def test_lower_layers_do_not_import_orchestration_or_unrelated_layers() -> None:
    forbidden = {
        "models": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
            "sources",
        },
        "bundle_paths": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
            "sources",
        },
        "sources": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
        },
        "bundles": {
            "application",
            "execution",
            "payload_files",
            "sources",
        },
        "parser": {
            "application",
            "bundles",
            "execution",
            "payload_files",
            "sources",
        },
        "payload_files": {
            "application",
            "bundles",
            "execution",
            "parser",
            "sources",
        },
        "execution": {
            "application",
            "bundles",
            "parser",
            "payload_files",
            "sources",
        },
    }

    for module_name, disallowed in forbidden.items():
        assert _local_imports(module_name).isdisjoint(disallowed), module_name


def test_cli_depends_on_application_not_source_or_legacy_modules() -> None:
    imports = _local_imports("cli")

    assert "application" in imports
    assert "sources" not in imports
    assert "input" not in imports
    assert "files" not in imports


def test_legacy_facade_modules_are_removed() -> None:
    assert not (PACKAGE_ROOT / "input.py").exists()
    assert not (PACKAGE_ROOT / "files.py").exists()


def test_runtime_module_dependencies_are_acyclic() -> None:
    modules = {
        path.stem
        for path in PACKAGE_ROOT.glob("*.py")
        if path.stem != "__init__"
    }
    graph = {
        module: _local_imports(module) & modules
        for module in modules
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            raise AssertionError(f"cyclic PatchHarbor import at {module}")
        if module in visited:
            return
        visiting.add(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.remove(module)
        visited.add(module)

    for module in sorted(modules):
        visit(module)
