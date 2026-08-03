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
            "presentation",
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
            "presentation",
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
            "presentation",
        },
        "bundles": {
            "application",
            "execution",
            "interpreters",
            "payload_files",
            "platform",
            "presentation",
            "sources",
        },
        "parser": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "payload_files",
            "platform",
            "presentation",
            "sources",
        },
        "payload_files": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "platform",
            "presentation",
            "sources",
        },
        "interpreters": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
            "platform",
            "presentation",
            "sources",
        },
        "output": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "payload_files",
            "platform",
            "presentation",
            "sources",
        },
        "run_log": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "output",
            "parser",
            "payload_files",
            "platform",
            "presentation",
            "sources",
        },
        "execution": {
            "application",
            "bundles",
            "parser",
            "payload_files",
            "presentation",
            "sources",
        },
        "presentation": {
            "application",
            "bundles",
            "execution",
            "interpreters",
            "parser",
            "payload_files",
            "platform",
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
        "presentation",
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


def test_execution_delegates_binary_output_capture_to_output_module() -> None:
    execution_source = (PACKAGE_ROOT / "execution.py").read_text(
        encoding="utf-8"
    )
    output_source = (PACKAGE_ROOT / "output.py").read_text(encoding="utf-8")

    assert "from patchharbor.output import OutputTargets, ProcessOutputCapture" in execution_source
    assert "RollingLineBuffer" not in execution_source
    assert "threading" not in execution_source
    assert "codecs" not in execution_source
    assert "Thread(" in output_source

    for platform_module in ("posix.py", "windows.py"):
        source = (PACKAGE_ROOT / "platform" / platform_module).read_text(
            encoding="utf-8"
        )
        assert "stdout=subprocess.PIPE" in source
        assert "stderr=subprocess.STDOUT" in source
        assert "text=True" not in source
        assert "encoding=" not in source
        assert "errors=" not in source


def test_execution_output_contract_does_not_import_run_log() -> None:
    execution_imports = _local_imports("execution")
    output_imports = _local_imports("output")

    assert "output" in execution_imports
    assert "run_log" not in execution_imports
    assert "run_log" not in output_imports


def test_cli_coordinates_output_and_run_log_boundaries() -> None:
    imports = _local_imports("cli")

    assert "application" in imports
    assert "output" in imports
    assert "presentation" in imports
    assert "run_log" in imports


def test_execution_does_not_import_terminal_presentation() -> None:
    assert "presentation" not in _local_imports("execution")
    assert "presentation" not in _local_imports("output")
    assert "presentation" in _local_imports("application")


def test_dashboard_state_remains_inside_presentation_boundary() -> None:
    for module_name in ("application", "execution", "output"):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(encoding="utf-8")
        assert "DashboardSnapshot" not in source
        assert "TerminalDashboard" not in source

    assert "presentation" not in _local_imports("execution")
    assert "presentation" not in _local_imports("output")
