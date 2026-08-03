from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib
import zipfile

import pytest

from patchharbor import __version__
from tests.platform_support import PROJECT_ROOT, native_script, native_value


pytestmark = pytest.mark.packaging

MAX_WHEEL_BYTES = 256 * 1024
RELEASE_VERSION = "1.0.0"


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _project_metadata() -> dict[str, object]:
    return tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]


def test_release_metadata_is_complete_and_runtime_has_no_dependencies() -> None:
    project = _project_metadata()

    assert __version__ == RELEASE_VERSION
    assert project["name"] == "patchharbor"
    assert project["dynamic"] == ["version"]
    assert project["requires-python"] == ">=3.12"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert project["dependencies"] == []
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert (PROJECT_ROOT / "LICENSE").is_file()


def test_release_distributions_run_after_pipx_installation(tmp_path: Path) -> None:
    distribution_dir = tmp_path / "dist"
    build = _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--no-isolation",
            "--outdir",
            str(distribution_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(distribution_dir.glob("patchharbor-*.whl"))
    source_distributions = list(distribution_dir.glob("patchharbor-*.tar.gz"))
    assert [path.name for path in wheels] == [
        f"patchharbor-{RELEASE_VERSION}-py3-none-any.whl"
    ]
    assert [path.name for path in source_distributions] == [
        f"patchharbor-{RELEASE_VERSION}.tar.gz"
    ]
    assert wheels[0].stat().st_size <= MAX_WHEEL_BYTES

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        metadata = wheel.read(metadata_name).decode("utf-8")
        assert f"Version: {RELEASE_VERSION}\n" in metadata
        assert "License-Expression: MIT\n" in metadata
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
        assert "patchharbor/cli.py" in names

    with tarfile.open(source_distributions[0], "r:gz") as source_distribution:
        names = set(source_distribution.getnames())
        root = f"patchharbor-{RELEASE_VERSION}"
        for required in (
            f"{root}/LICENSE",
            f"{root}/README.md",
            f"{root}/pyproject.toml",
            f"{root}/src/patchharbor/cli.py",
        ):
            assert required in names

    pipx_home = tmp_path / "pipx-home"
    pipx_bin = tmp_path / "pipx-bin"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "PIPX_HOME": str(pipx_home),
            "PIPX_BIN_DIR": str(pipx_bin),
            "PIPX_MAN_DIR": str(tmp_path / "pipx-man"),
            "PIPX_DEFAULT_PYTHON": sys.executable,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    install = _run(
        [
            sys.executable,
            "-m",
            "pipx",
            "install",
            "--python",
            sys.executable,
            str(wheels[0]),
        ],
        cwd=tmp_path,
        environment=environment,
    )

    assert install.returncode == 0, install.stdout + install.stderr

    executable_name = native_value("patchharbor", "patchharbor.exe")
    executable = pipx_bin / executable_name
    empty_workdir = tmp_path / "empty-workdir"
    empty_workdir.mkdir()
    assert list(empty_workdir.iterdir()) == []

    version_result = _run(
        [str(executable), "--version"],
        cwd=empty_workdir,
        environment=environment,
    )
    assert version_result.returncode == 0
    assert version_result.stdout == f"patchharbor {RELEASE_VERSION}\n"
    assert version_result.stderr == ""

    help_result = _run(
        [str(executable), "--help"],
        cwd=empty_workdir,
        environment=environment,
    )
    assert help_result.returncode == 0
    assert "usage: patchharbor" in help_result.stdout
    assert "--version" in help_result.stdout
    assert "fs" in help_result.stdout

    run_help = _run(
        [str(executable), "fs", "run", "--help"],
        cwd=empty_workdir,
        environment=environment,
    )
    assert run_help.returncode == 0
    for expected in (
        "# PATCHHARBOR",
        "ZIP PatchBundles may contain ordered scripts and binary payload files.",
        "Scripts run in the current working directory.",
        "--timeout SECONDS",
        "--plain",
        "--no-color",
        "--log",
    ):
        assert expected in run_help.stdout
    for deferred in ("websocket", "clipboard", "ssh", "save mode"):
        assert deferred not in run_help.stdout.lower()

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    script_suffix = native_value(".sh", ".ps1")
    script_path = source_dir / f"release-smoke{script_suffix}"
    script_path.write_text(
        native_script(
            'printf "%s\\n" "release-smoke"\n'
            'printf "%s" "cwd-ok" > release-cwd.txt',
            'Write-Output "release-smoke"\n'
            '[System.IO.File]::WriteAllText("release-cwd.txt", "cwd-ok")',
        ),
        encoding="utf-8",
    )

    run_result = _run(
        [str(executable), "fs", "run", str(script_path)],
        cwd=empty_workdir,
        environment=environment,
    )

    assert run_result.returncode == 0
    assert run_result.stdout == "release-smoke\n"
    assert run_result.stderr == ""
    assert (empty_workdir / "release-cwd.txt").read_text(encoding="utf-8") == (
        "cwd-ok"
    )
