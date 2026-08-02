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
            "interpreters",
            "parser",
            "payload_files",
            "platform",
            "sources",
        },
        "bundle_paths": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "payload_files",
            "platform",
            "sources",
        },
        "sources": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "payload_files",
            "platform",
        },
        "bundles": {
            "application",
            "execution",
            "interpreters",
            "payload_files",
            "platform",
            "sources",
        },
        "parser": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "payload_files",
            "platform",
            "sources",
        },
        "payload_files": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "platform",
            "sources",
        },
        "interpreters": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
            "platform",
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


def test_execution_uses_only_the_platform_lifecycle_boundary() -> None:
    imports = _local_imports("execution")
    source = (PACKAGE_ROOT / "execution.py").read_text(encoding="utf-8")

    assert "platform" in imports
    assert "patchharbor.platform.posix" not in source
    assert "patchharbor.platform.windows" not in source
    assert "ctypes" not in source
    assert "killpg" not in source
    assert "CTRL_BREAK_EVENT" not in source
    assert "start_new_session" not in source
    assert "process_tree.wait(" not in source
    assert "process_tree.stop(" not in source
    assert "process_tree.run(" in source


def test_platform_package_does_not_import_application_layers() -> None:
    disallowed = {
        "application",
        "bundles",
        "cli",
        "execution",
        "interpreters",
        "parser",
        "payload_files",
        "sources",
    }
    imports: set[str] = set()

    for module_path in (PACKAGE_ROOT / "platform").glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("patchharbor."):
                    imports.add(node.module.split(".", 1)[1].split(".", 1)[0])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("patchharbor."):
                        imports.add(
                            alias.name.split(".", 1)[1].split(".", 1)[0]
                        )

    assert imports.isdisjoint(disallowed)
