# PATCHHARBOR.13b4 – Packaging Acceptance

This document records acceptance for the PatchHarbor packaging hardening series.

The accepted scope is the target package metadata, installation documentation, and pipx smoke harness created by PATCHHARBOR.13b1 through PATCHHARBOR.13b3.

## Accepted predecessor patches

| Patch | Commit | Accepted artifact |
| --- | --- | --- |
| PATCHHARBOR.13b1 | `Harden PatchHarbor pyproject metadata` | `pyproject.toml` metadata and packaging metadata tests |
| PATCHHARBOR.13b2 | `Document PatchHarbor installation` | README installation section and README installation tests |
| PATCHHARBOR.13b3 | `Add pipx smoke script` | isolated pipx smoke script and dry-run tests |

## Packaging acceptance gates

PATCHHARBOR.13b4 accepts the packaging work when all of these gates are true:

1. `pyproject.toml` declares the `patchharbor` project.
2. `pyproject.toml` declares the `patchharbor = "patchharbor.cli:main"` console script.
3. `pyproject.toml` uses the `src` package layout for `patchharbor*`.
4. `src/patchharbor/__main__.py` supports `python -m patchharbor`.
5. `README.md` documents virtual-environment installation.
6. `README.md` documents isolated `pipx install -e .` installation.
7. `README.md` documents refreshing a local pipx install.
8. `scripts/smoke_pipx_install.sh` exists and is executable.
9. `scripts/smoke_pipx_install.sh --dry-run` prints the pipx install and CLI smoke plan without requiring pipx.
10. The smoke plan includes `patchharbor --help`.
11. The smoke plan includes `patchharbor --version`.
12. The smoke plan includes `patchharbor doctor --repo`.
13. The smoke plan includes `patchharbor check-env --repo`.
14. Packaging-related tests are functional tests, not terminal-layout snapshots.

## Functional verification commands

The acceptance command set is:

    python3 -m unittest tests.test_packaging_metadata
    python3 -m unittest tests.test_readme_installation
    python3 -m unittest tests.test_pipx_smoke_script
    scripts/smoke_pipx_install.sh --dry-run --repo . --pipx __patchharbor_missing_pipx__
    python3 -m patchharbor --help
    python3 -m patchharbor --version
    python3 -m patchharbor doctor --repo .
    python3 -m patchharbor check-env --repo . --no-defaults

A real pipx smoke may also be run locally when pipx is installed:

    scripts/smoke_pipx_install.sh --repo .

The real smoke intentionally uses temporary `PIPX_HOME`, `PIPX_BIN_DIR`, and `PIPX_MAN_DIR` values so it does not modify the user's normal pipx environment.

## Acceptance boundaries

This acceptance does not mean PatchHarbor is fully released. It only means the packaging hardening series is complete enough to move to source cleanup inventory.

Source cleanup begins with PATCHHARBOR.14a1 and must remain inventory-first.

## Display-test policy

Exact terminal formatting is not part of this packaging acceptance.

Do not fail packaging acceptance only because of:

- command wrapping
- help text line wrapping
- color output
- display-only indentation
- progress/context placement

Functional status, command availability, return codes, and install-smoke behavior remain testable contracts.

## Non-goals for PATCHHARBOR.13b4

This patch does not:

- change `pyproject.toml`
- change package metadata
- change README installation instructions
- change pipx smoke behavior
- run a real pipx install
- change CLI behavior
- change source-side wrappers
- change source-side aliases
- change `c`
- change `r`
- remove source-side files
- add display-only assertions

## Next step

After PATCHHARBOR.13b4 is green, the next operative milestone is:

    PATCHHARBOR.14a1 – RepoDossier Script Cleanup Inventory

That next step is source-only and must not delete old source scripts before cleanup safety tests prove replacement coverage.
