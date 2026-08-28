#!/usr/bin/env python3
"""Build PatchHarbor release artifacts from a clean staged source tree."""

from __future__ import annotations

import argparse
from configparser import ConfigParser
from email.message import Message
from email.parser import BytesParser
from email.policy import default as default_email_policy
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from typing import NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_INPUT_FILES = (
    "CHAT_INSTRUCTIONS.md",
    "LICENSE",
    "README.md",
    "pyproject.toml",
)
_RELEASE_INPUT_TREES = ("src",)
_FORBIDDEN_STAGED_ROOTS = {"build", "dist"}
_FORBIDDEN_STAGED_PARTS = {"__pycache__"}
_FORBIDDEN_STAGED_SUFFIXES = {".pyc", ".pyo"}


class _DistributionContract(NamedTuple):
    metadata: tuple[tuple[str, tuple[str, ...]], ...]
    description_lines: tuple[str, ...]
    scripts: tuple[tuple[str, str], ...]

    @property
    def name(self) -> str:
        return self._single_header("name")

    @property
    def version(self) -> str:
        return self._single_header("version")

    def _single_header(self, name: str) -> str:
        values = dict(self.metadata).get(name, ())
        if len(values) != 1:
            raise RuntimeError(
                f"release metadata must contain exactly one {name!r} header"
            )
        return values[0]


def _assert_clean_release_stage(destination: Path) -> None:
    for path in destination.rglob("*"):
        relative = path.relative_to(destination)
        if (
            relative.parts[0] in _FORBIDDEN_STAGED_ROOTS
            or any(
                part in _FORBIDDEN_STAGED_PARTS
                or part.endswith(".egg-info")
                for part in relative.parts
            )
        ):
            raise RuntimeError(f"forbidden release-stage path: {relative}")
        if path.is_file() and path.suffix in _FORBIDDEN_STAGED_SUFFIXES:
            raise RuntimeError(f"forbidden release-stage file: {relative}")


def _metadata_contract(raw_metadata: bytes) -> tuple[
    tuple[tuple[str, tuple[str, ...]], ...],
    tuple[str, ...],
]:
    message = BytesParser(policy=default_email_policy).parsebytes(raw_metadata)
    assert isinstance(message, Message)
    names = sorted({name.lower() for name in message.keys()})
    headers = tuple(
        (
            name,
            tuple(str(value) for value in message.get_all(name, [])),
        )
        for name in names
    )
    payload = message.get_payload()
    if not isinstance(payload, str):
        raise RuntimeError("release metadata description must be text")
    return headers, tuple(payload.splitlines())


def _wheel_contract(wheel: Path) -> _DistributionContract:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        entry_point_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(metadata_names) != 1 or len(entry_point_names) != 1:
            raise RuntimeError(
                "wheel must contain exactly one METADATA and entry_points.txt"
            )
        metadata, description = _metadata_contract(
            archive.read(metadata_names[0])
        )
        parser = ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(
            archive.read(entry_point_names[0]).decode("utf-8")
        )
        if parser.sections() != ["console_scripts"]:
            raise RuntimeError("wheel contains unexpected entry-point groups")
        scripts = tuple(sorted(parser.items("console_scripts")))
    return _DistributionContract(metadata, description, scripts)


def _source_distribution_contract(
    source_distribution: Path,
) -> _DistributionContract:
    with tarfile.open(source_distribution, "r:gz") as archive:
        members = archive.getmembers()
        roots = {
            member.name.split("/", 1)[0]
            for member in members
            if member.name
        }
        if len(roots) != 1:
            raise RuntimeError("source distribution must contain one root directory")
        root = next(iter(roots))
        metadata_member = archive.getmember(f"{root}/PKG-INFO")
        pyproject_member = archive.getmember(f"{root}/pyproject.toml")
        metadata_file = archive.extractfile(metadata_member)
        pyproject_file = archive.extractfile(pyproject_member)
        if metadata_file is None or pyproject_file is None:
            raise RuntimeError("source distribution metadata is unreadable")
        metadata, description = _metadata_contract(metadata_file.read())
        pyproject = tomllib.loads(pyproject_file.read().decode("utf-8"))
        project = pyproject.get("project")
        if not isinstance(project, dict):
            raise RuntimeError("source distribution has no project metadata")
        raw_scripts = project.get("scripts")
        if not isinstance(raw_scripts, dict) or not all(
            isinstance(name, str) and isinstance(target, str)
            for name, target in raw_scripts.items()
        ):
            raise RuntimeError("source distribution scripts are invalid")
        scripts = tuple(sorted(raw_scripts.items()))
    return _DistributionContract(metadata, description, scripts)


def _packaged_chat_instructions(
    wheel: Path,
    source_distribution: Path,
) -> tuple[bytes, bytes]:
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = [
            name
            for name in archive.namelist()
            if name.endswith(
                ".data/data/share/patchharbor/CHAT_INSTRUCTIONS.md"
            )
        ]
        if len(wheel_names) != 1:
            raise RuntimeError(
                "wheel must contain exactly one CHAT_INSTRUCTIONS.md data file"
            )
        wheel_document = archive.read(wheel_names[0])

    with tarfile.open(source_distribution, "r:gz") as archive:
        roots = {
            member.name.split("/", 1)[0]
            for member in archive.getmembers()
            if member.name
        }
        if len(roots) != 1:
            raise RuntimeError(
                "source distribution must contain one root directory"
            )
        root = next(iter(roots))
        try:
            member = archive.getmember(f"{root}/CHAT_INSTRUCTIONS.md")
        except KeyError as exc:
            raise RuntimeError(
                "source distribution is missing CHAT_INSTRUCTIONS.md"
            ) from exc
        source_file = archive.extractfile(member)
        if source_file is None:
            raise RuntimeError(
                "source-distribution CHAT_INSTRUCTIONS.md is unreadable"
            )
        source_document = source_file.read()

    return wheel_document, source_document


def _audit_release_artifacts(wheel: Path, source_distribution: Path) -> None:
    wheel_contract = _wheel_contract(wheel)
    source_contract = _source_distribution_contract(source_distribution)
    if wheel_contract != source_contract:
        raise RuntimeError(
            "wheel and source distribution metadata or entry points differ"
        )
    if wheel_contract.name != "patchharbor":
        raise RuntimeError("release artifact has an unexpected project name")
    version = wheel_contract.version
    if wheel.name != f"patchharbor-{version}-py3-none-any.whl":
        raise RuntimeError("wheel filename does not match release metadata")
    if source_distribution.name != f"patchharbor-{version}.tar.gz":
        raise RuntimeError(
            "source-distribution filename does not match release metadata"
        )

    expected_chat = (PROJECT_ROOT / "CHAT_INSTRUCTIONS.md").read_bytes()
    wheel_chat, source_chat = _packaged_chat_instructions(
        wheel,
        source_distribution,
    )
    if wheel_chat != expected_chat or source_chat != expected_chat:
        raise RuntimeError(
            "release artifacts do not contain the canonical chat instructions"
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

    _assert_clean_release_stage(destination)


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
    wheel, source_distribution = wheels[0], source_distributions[0]
    _audit_release_artifacts(wheel, source_distribution)
    return wheel, source_distribution


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
