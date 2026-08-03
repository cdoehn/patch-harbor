#!/usr/bin/env python3
"""Build PatchHarbor release artifacts from a clean staged source tree."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_INPUT_FILES = (
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "pyproject.toml",
)
_RELEASE_INPUT_TREES = (
    "src",
    "tests",
)


def _copy_release_inputs(destination: Path) -> None:
    for relative_name in _RELEASE_INPUT_FILES:
        source = PROJECT_ROOT / relative_name
        if not source.is_file():
            raise FileNotFoundError(f"missing release input: {relative_name}")
        shutil.copy2(source, destination / relative_name)

    for relative_name in _RELEASE_INPUT_TREES:
        source = PROJECT_ROOT / relative_name
        if not source.is_dir():
            raise FileNotFoundError(f"missing release input: {relative_name}")
        shutil.copytree(
            source,
            destination / relative_name,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "*.pyo",
                "*.egg-info",
            ),
        )

    scripts_directory = destination / "scripts"
    scripts_directory.mkdir()
    shutil.copy2(Path(__file__), scripts_directory / Path(__file__).name)


def _remove_previous_project_artifacts(output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for pattern in ("patchharbor-*.whl", "patchharbor-*.tar.gz"):
        for artifact in output_directory.glob(pattern):
            artifact.unlink()


def build_release(output_directory: Path) -> tuple[Path, Path]:
    """Build one wheel and one source distribution into *output_directory*."""
    output_directory = output_directory.resolve()
    _remove_previous_project_artifacts(output_directory)

    with tempfile.TemporaryDirectory(prefix="patchharbor-release-") as raw_stage:
        stage = Path(raw_stage)
        _copy_release_inputs(stage)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--sdist",
                "--no-isolation",
                "--outdir",
                str(output_directory),
            ],
            cwd=stage,
            check=True,
        )

    wheels = sorted(output_directory.glob("patchharbor-*.whl"))
    source_distributions = sorted(
        output_directory.glob("patchharbor-*.tar.gz")
    )
    if len(wheels) != 1 or len(source_distributions) != 1:
        raise RuntimeError(
            "release build did not produce exactly one wheel and one "
            "source distribution"
        )
    return wheels[0], source_distributions[0]


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build PatchHarbor from a clean staged source tree."
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="artifact output directory (default: repository dist directory)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()
    wheel, source_distribution = build_release(arguments.outdir)
    print(wheel)
    print(source_distribution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
