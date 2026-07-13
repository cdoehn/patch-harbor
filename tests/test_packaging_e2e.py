from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"


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

    executable_name = "patchharbor.exe" if os.name == "nt" else "patchharbor"
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
    script_suffix = ".ps1" if os.name == "nt" else ".sh"
    script_path = workdir / f"hello{script_suffix}"
    if os.name == "nt":
        script_body = 'Write-Output "pipx-e2e"\n'
    else:
        script_body = 'printf "%s\\n" "pipx-e2e"\n'
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
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
