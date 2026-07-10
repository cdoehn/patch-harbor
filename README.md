# PatchHarbor

PatchHarbor is a small development-tools repository for reusable patch workflow helpers, repository maintenance scripts, and local development automation.

The project starts as the migration target for development scripts that previously lived inside RepoDossier. The goal is to make those tools repository-agnostic before multiple projects depend on them.

## Current status

PatchHarbor is in active migration hardening. The package skeleton, CLI surface, runner, public-audit helpers, environment-check helpers, export models, and packaging metadata now exist in the target repository.

Completed so far:

- standalone Git target repository exists
- Python package metadata exists in pyproject.toml
- console and module CLI entry points exist
- generic patch-runner, lint, public-audit, environment-check, and export helper models exist
- source-side compatibility wrappers are being adopted incrementally

Still migration-sensitive:

- source cleanup must only happen after parity tests prove the replacement
- packaging/install smoke checks are still being hardened

## Migration boundary

RepoDossier remains the source repository for the existing development scripts until each tool has been extracted, generalized, tested, and wired back through a thin compatibility wrapper where needed.

PatchHarbor must not store contributor-specific home paths, private e-mail addresses, workstation names, or local machine assumptions in tracked files.

## Installation

PatchHarbor is a Python package using a `src` layout and the console script `patchharbor`.

Requirements:

- Python 3.12 or newer
- Git
- `pipx` for isolated command-line installation, or a virtual environment for editable development

For local development from a checkout:

    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e ".[dev]"
    python3 -m patchharbor --help
    python3 -m patchharbor doctor --repo .

For an isolated command-line install from the current checkout:

    pipx install -e .
    patchharbor --help
    patchharbor doctor --repo .

To refresh an existing isolated install after local changes:

    pipx uninstall patchharbor
    pipx install -e .

The package also supports module execution without relying on the console script:

    python3 -m patchharbor --help
    python3 -m patchharbor --version

After installation, the current target-side command surface is:

- `patchharbor doctor`
- `patchharbor lint-script`
- `patchharbor run-script`
- `patchharbor audit-public`
- `patchharbor check-env`

## Installation

PatchHarbor is a Python package using a `src` layout and the console script `patchharbor`.

Requirements:

- Python 3.12 or newer
- Git
- `pipx` for isolated command-line installation, or a virtual environment for editable development

For local development from a checkout:

    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e ".[dev]"
    python3 -m patchharbor --help
    python3 -m patchharbor doctor --repo .

For an isolated command-line install from the current checkout:

    pipx install -e .
    patchharbor --help
    patchharbor doctor --repo .

To refresh an existing isolated install after local changes:

    pipx uninstall patchharbor
    pipx install -e .

The package also supports module execution without relying on the console script:

    python3 -m patchharbor --help
    python3 -m patchharbor --version

After installation, the current target-side command surface is:

- `patchharbor doctor`
- `patchharbor lint-script`
- `patchharbor run-script`
- `patchharbor audit-public`
- `patchharbor check-env`

## Installation

PatchHarbor is a Python package using a `src` layout and the console script `patchharbor`.

Requirements:

- Python 3.12 or newer
- Git
- `pipx` for isolated command-line installation, or a virtual environment for editable development

For local development from a checkout:

    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e ".[dev]"
    python3 -m patchharbor --help
    python3 -m patchharbor doctor --repo .

For an isolated command-line install from the current checkout:

    pipx install -e .
    patchharbor --help
    patchharbor doctor --repo .

To refresh an existing isolated install after local changes:

    pipx uninstall patchharbor
    pipx install -e .

The package also supports module execution without relying on the console script:

    python3 -m patchharbor --help
    python3 -m patchharbor --version

After installation, the current target-side command surface is:

- `patchharbor doctor`
- `patchharbor lint-script`
- `patchharbor run-script`
- `patchharbor audit-public`
- `patchharbor check-env`

## Development

Use the editable install from the installation section, then run the functional test suite:

    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 -m pytest --color=yes

Useful smoke checks:

    python3 -m patchharbor --help
    python3 -m patchharbor --version
    python3 -m patchharbor doctor --repo .
    python3 -m patchharbor check-env --repo . --no-defaults

## Next migration step
Continue packaging hardening with a pipx smoke script and packaging acceptance documentation before starting source cleanup.
