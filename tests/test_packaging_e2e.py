from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tomllib

from tests.platform_support import PROJECT_ROOT, native_script, native_value


MAX_WHEEL_BYTES = 256 * 1024


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


def test_runtime_package_declares_no_third_party_dependencies() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project.get("dependencies", []) == []


def test_local_wheel_runs_after_pipx_installation(tmp_path: Path) -> None:
    distribution_dir = tmp_path / "dist"
    build = _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(distribution_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(distribution_dir.glob("patchharbor-*.whl"))
    assert len(wheels) == 1
    assert wheels[0].stat().st_size <= MAX_WHEEL_BYTES

    pipx_home = tmp_path / "pipx-home"
    pipx_bin = tmp_path / "pipx-bin"
    environment = os.environ.copy()
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
    help_result = _run(
        [str(executable), "--help"],
        cwd=tmp_path,
        environment=environment,
    )

    assert help_result.returncode == 0
    assert "usage: patchharbor" in help_result.stdout

    workdir = tmp_path / "work"
    workdir.mkdir()
    script_suffix = native_value(".sh", ".ps1")
    script_path = workdir / f"hello{script_suffix}"
    script_path.write_text(
        native_script(
            'printf "%s\\n" "pipx-e2e"',
            'Write-Output "pipx-e2e"',
        ),
        encoding="utf-8",
    )

    run_result = _run(
        [str(executable), "fs", "run", str(script_path)],
        cwd=workdir,
        environment=environment,
    )

    assert run_result.returncode == 0
    assert run_result.stdout == "pipx-e2e\n"
    assert run_result.stderr == ""
