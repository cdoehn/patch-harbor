from __future__ import annotations

import ast
from pathlib import Path
import sys


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


def _called_name(expression: ast.expr) -> str | None:
    if not isinstance(expression, ast.Call):
        return None
    function = expression.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _repository_lock_without_registry_lock(
    statements: list[ast.stmt],
    *,
    registry_owned: bool = False,
) -> bool:
    for statement in statements:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _repository_lock_without_registry_lock(statement.body):
                return True
        elif isinstance(statement, ast.With):
            names = {
                _called_name(item.context_expr)
                for item in statement.items
            }
            owns_registry = registry_owned or "registry_lock" in names
            if "repository_lock" in names and not owns_registry:
                return True
            if _repository_lock_without_registry_lock(
                statement.body,
                registry_owned=owns_registry,
            ):
                return True
        elif isinstance(statement, (ast.If, ast.For, ast.While, ast.Try)):
            branches = [statement.body, statement.orelse]
            if isinstance(statement, ast.Try):
                branches.extend(handler.body for handler in statement.handlers)
                branches.append(statement.finalbody)
            if any(
                _repository_lock_without_registry_lock(
                    branch,
                    registry_owned=registry_owned,
                )
                for branch in branches
            ):
                return True
    return False


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
        "resource_policy": {
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
            "presentation",
        },
        "bundles": {
            "application",
            "execution",
            "interpreters",
            "payload_files",
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
            "presentation",
            "sources",
        },
        "interpreters": {
            "application",
            "bundles",
            "execution",
            "parser",
            "payload_files",
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



def test_registration_layers_have_one_directional_dependency_flow() -> None:
    assert _local_imports("registration") == {
        "errors",
        "models",
        "locks",
        "registry",
        "repository",
        "user_paths",
    }
    assert _local_imports("registry") == {
        "errors",
        "models",
        "platform",
        "user_paths",
    }
    assert _local_imports("repository") == {
        "errors",
        "git_commands",
        "models",
        "physical_paths",
        "platform",
    }
    assert _local_imports("git_commands") == {"errors"}
    assert _local_imports("git_capture") == {
        "errors",
        "git_commands",
        "models",
        "repository_paths",
    }
    assert _local_imports("repository_paths") == {"errors", "models"}
    assert _local_imports("state_fingerprint") == set()
    assert _local_imports("context_output") == {"models"}
    assert _local_imports("repository_state") == {
        "errors",
        "git_capture",
        "git_commands",
        "locks",
        "models",
        "registry",
        "repository",
        "repository_paths",
        "state_fingerprint",
        "user_paths",
    }
    assert _local_imports("result_bundle") == {
        "errors",
        "git_commands",
        "locks",
        "models",
        "physical_paths",
        "registry",
        "repository",
        "repository_paths",
        "repository_state",
        "user_paths",
    }
    assert _local_imports("locks") == {
        "errors",
        "models",
        "platform",
        "user_paths",
    }
    assert _local_imports("user_paths") == {
        "errors",
        "physical_paths",
    }
    assert _local_imports("physical_paths") == set()


def test_git_processes_are_confined_to_the_canonical_command_boundary() -> None:
    command_source = (PACKAGE_ROOT / "git_commands.py").read_text(
        encoding="utf-8"
    )
    assert "subprocess.run" in command_source

    for module_name in (
        "repository",
        "repository_state",
        "git_capture",
        "result_bundle",
    ):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(
            encoding="utf-8"
        )
        assert "import subprocess" not in source
        assert "subprocess.run" not in source


def test_lock_mechanics_are_confined_to_the_platform_boundary() -> None:
    platform_source = (
        PACKAGE_ROOT / "platform" / "locking.py"
    ).read_text(encoding="utf-8")
    assert "fcntl" in platform_source
    assert "msvcrt" in platform_source

    lock_source = (PACKAGE_ROOT / "locks.py").read_text(encoding="utf-8")
    assert "patchharbor.platform.locking" in lock_source

    for module_name in ("locks", "registry"):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(
            encoding="utf-8"
        )
        assert "fcntl" not in source
        assert "msvcrt" not in source
        assert "import os" not in source


def test_registration_never_acquires_repository_lock_before_registry_lock() -> None:
    tree = ast.parse(
        (PACKAGE_ROOT / "registration.py").read_text(encoding="utf-8")
    )
    assert not _repository_lock_without_registry_lock(tree.body)


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


def test_platform_package_uses_the_shared_windows_boundary() -> None:
    source = (PACKAGE_ROOT / "platform" / "__init__.py").read_text(
        encoding="utf-8"
    )

    assert "is_windows()" in source
    assert "import os" not in source


def test_execution_delegates_binary_output_capture_to_output_module() -> None:
    execution_source = (PACKAGE_ROOT / "execution.py").read_text(
        encoding="utf-8"
    )
    output_source = (PACKAGE_ROOT / "output.py").read_text(encoding="utf-8")

    assert (
        "from patchharbor.output import OutputTargets, ProcessOutputCapture"
        in execution_source
    )
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


def test_cli_coordinates_only_public_composition_boundaries() -> None:
    imports = _local_imports("cli")

    assert imports == {
        "application",
        "context_output",
        "errors",
        "execution",
        "output",
        "platform",
        "presentation",
        "run_log",
    }


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


def test_platform_sensitive_modules_use_only_the_platform_boundary() -> None:
    interpreters_source = (PACKAGE_ROOT / "interpreters.py").read_text(encoding="utf-8")
    payload_source = (PACKAGE_ROOT / "payload_files.py").read_text(encoding="utf-8")

    assert "from patchharbor.platform.runtime import" in interpreters_source
    assert "import os" not in interpreters_source
    assert "import shutil" not in interpreters_source

    assert "from patchharbor.platform.filesystem import" in payload_source
    assert "import os" not in payload_source
    assert "import stat" not in payload_source
    assert "import tempfile" not in payload_source


def test_platform_error_text_is_normalized_outside_platform_modules() -> None:
    for module_name in ("bundles", "execution", "sources"):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(encoding="utf-8")
        assert "describe_os_error" in source


def test_runtime_package_imports_only_itself_and_the_standard_library() -> None:
    imported_roots: set[str] = set()
    for module_path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

    allowed = set(sys.stdlib_module_names) | {"__future__", "patchharbor"}
    assert imported_roots <= allowed


def test_resource_budgets_have_one_low_level_policy_boundary() -> None:
    policy_source = (PACKAGE_ROOT / "resource_policy.py").read_text(
        encoding="utf-8"
    )
    assert "class ResourcePolicy" in policy_source
    assert "DEFAULT_RESOURCE_POLICY" in policy_source

    for module_name in ("sources", "bundles", "application"):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(
            encoding="utf-8"
        )
        assert "patchharbor.resource_policy" in source

    payload_source = (PACKAGE_ROOT / "payload_files.py").read_text(
        encoding="utf-8"
    )
    assert "patchharbor.resource_policy" not in payload_source

    for module_name in ("sources", "bundles"):
        source = (PACKAGE_ROOT / f"{module_name}.py").read_text(
            encoding="utf-8"
        )
        assert "10 * 1024 * 1024" not in source
        assert "256 * 1024 * 1024" not in source
        assert "512 * 1024 * 1024" not in source
        assert "MAX_ZIP_ENTRIES" not in source
        assert "MAX_INPUT_ARTIFACT_BYTES" not in source
        assert "MAX_PAYLOAD_BYTES" not in source



def _qualified_module_name(path: Path) -> str | None:
    relative = path.relative_to(PACKAGE_ROOT)
    if relative.name == "__init__.py":
        if relative.parent == Path("."):
            return None
        return ".".join(relative.parent.parts)
    return ".".join(relative.with_suffix("").parts)


def _qualified_local_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        names: tuple[str, ...] = ()
        if isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        elif isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        for imported_name in names:
            if imported_name.startswith("patchharbor."):
                imports.add(imported_name.removeprefix("patchharbor."))
    return imports


def test_complete_runtime_dependency_graph_is_acyclic() -> None:
    modules_by_path = {
        path: module_name
        for path in PACKAGE_ROOT.rglob("*.py")
        if (module_name := _qualified_module_name(path)) is not None
    }
    module_names = set(modules_by_path.values())
    graph = {
        module_name: _qualified_local_imports(path) & module_names
        for path, module_name in modules_by_path.items()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_name: str) -> None:
        if module_name in visiting:
            raise AssertionError(
                f"cyclic PatchHarbor import at {module_name}"
            )
        if module_name in visited:
            return
        visiting.add(module_name)
        for dependency in graph[module_name]:
            visit(dependency)
        visiting.remove(module_name)
        visited.add(module_name)

    for module_name in sorted(graph):
        visit(module_name)
