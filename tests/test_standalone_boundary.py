from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "src" / "patchharbor"
EXTERNAL_PACKAGE = "repo" + "dossier"
EXTERNAL_SOURCE_ENV = "PATCHHARBOR_" + "SOURCE_REPO"


def _runtime_python_files() -> list[Path]:
    return sorted(RUNTIME_ROOT.rglob("*.py"))


def test_runtime_does_not_import_external_repository_package() -> None:
    imports: list[tuple[Path, str]] = []
    for path in _runtime_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append((path, node.module))

    coupled = [
        (str(path.relative_to(ROOT)), module)
        for path, module in imports
        if module == EXTERNAL_PACKAGE or module.startswith(EXTERNAL_PACKAGE + ".")
    ]
    assert coupled == []


def test_packaging_does_not_depend_on_external_repository_package() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies: list[str] = list(project.get("project", {}).get("dependencies", []))
    for values in project.get("project", {}).get("optional-dependencies", {}).values():
        dependencies.extend(values)

    normalized = [item.lower().replace("_", "-") for item in dependencies]
    assert not any(EXTERNAL_PACKAGE in item.replace("-", "") for item in normalized)


def test_runtime_does_not_require_external_source_checkout_environment() -> None:
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8") for path in _runtime_python_files()
    )
    assert EXTERNAL_SOURCE_ENV not in runtime_text
