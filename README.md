# PatchHarbor

<!-- badges:start -->
[![Docker Integration Tests](https://github.com/cdoehn/patch-harbor/actions/workflows/docker-integration-tests.yml/badge.svg?branch=main)](https://github.com/cdoehn/patch-harbor/actions/workflows/docker-integration-tests.yml)
![Python](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?logo=python&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04%20%7C%2026.04-E95420?logo=ubuntu&logoColor=white)
![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Repository](https://img.shields.io/badge/repository-private-lightgrey?logo=github)
<!-- badges:end -->

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
- `patchharbor rules`

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
- `patchharbor rules`

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
- `patchharbor rules`

## Development

Use the editable install from the installation section, then run the functional test suite:

    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 -m pytest --color=yes

Useful smoke checks:

    python3 -m patchharbor --help
    python3 -m patchharbor --version
    python3 -m patchharbor doctor --repo .
    python3 -m patchharbor check-env --repo . --no-defaults
    python3 -m patchharbor rules list

## Timeout-protected development commands

Use `scripts/run_with_timeout.sh` for tests, builds, linters, packaging checks,
installation checks, smoke tests, and other commands that could block
indefinitely. The wrapper requires GNU `timeout` and runs each attempt with a
bounded maximum duration.

General form:

    scripts/run_with_timeout.sh [options] -- COMMAND [ARG...]

Important options:

- `--timeout DURATION` sets the maximum runtime for one attempt.
- `--kill-after DURATION` sends `SIGKILL` if the command does not stop after
  the initial `SIGTERM`.
- `--attempts NUMBER` sets the total number of attempts, including the first
  run.
- `--retry-delay DURATION` waits before restarting a timed-out command.

Choose the values from the expected workload rather than using one global
timeout. A focused unit test can normally use a shorter limit than a complete
test suite, package build, installation test, or container integration test.
Keep the number of attempts bounded.

For example, run focused tests with a two-minute limit per attempt:

    scripts/run_with_timeout.sh \
      --timeout 2m \
      --kill-after 10s \
      --attempts 2 \
      --retry-delay 2s \
      -- python3 -m unittest tests.test_run_with_timeout_script

The wrapper retries only exit statuses that indicate a timeout. Ordinary
command failures are returned immediately. Its internal retries use the same
timeout. When the selected limit was plausibly too short rather than the
process being stuck, invoke the wrapper again with a larger bounded timeout,
for example:

    scripts/run_with_timeout.sh \
      --timeout 5m \
      --kill-after 15s \
      --attempts 1 \
      -- python3 -m unittest discover -s tests -p 'test_*.py'

Do not increase the timeout indefinitely. Report the chosen timeout, attempt
count, and final result so that a real hang is not mistaken for a slow but
healthy command.

## Next migration step
Continue packaging hardening with a pipx smoke script and packaging acceptance documentation before starting source cleanup.
