# PatchHarbor

PatchHarbor is a small development-tools repository for reusable patch workflow helpers, repository maintenance scripts, and local development automation.

The project starts as the migration target for development scripts that previously lived inside RepoDossier. The goal is to make those tools repository-agnostic before multiple projects depend on them.

## Current status

PatchHarbor is in the bootstrap phase.

Completed so far:

- standalone Git target repository exists
- initial bootstrap note exists in docs/bootstrap.md
- project metadata exists in pyproject.toml

Not migrated yet:

- patch runner commands
- export runner commands
- patch metadata validators
- patch workflow rules
- RepoDossier compatibility wrappers

## Migration boundary

RepoDossier remains the source repository for the existing development scripts until each tool has been extracted, generalized, tested, and wired back through a thin compatibility wrapper where needed.

PatchHarbor must not store contributor-specific home paths, private e-mail addresses, workstation names, or local machine assumptions in tracked files.

## Development

Create a virtual environment when needed:

    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e ".[dev]"

Run tests after the package skeleton exists:

    python3 -m pytest --color=yes

## Next migration step

Add a minimal Python package and CLI skeleton, then add baseline tests before any RepoDossier development script is copied or generalized.
