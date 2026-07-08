# PatchHarbor migration baseline

PatchHarbor is the new standalone home for repository-agnostic development scripts and patch workflow helpers.

This repository starts as a small, tested target baseline. Existing project-specific scripts stay in their source repositories until each script or helper has been extracted, generalized, tested, and adopted through a thin compatibility wrapper.

## Current baseline

The target repository currently provides:

- Python project metadata in pyproject.toml.
- A minimal patchharbor package under src/patchharbor.
- A patchharbor CLI with help, version, and doctor checks.
- Baseline tests for CLI behavior, project metadata, and private-value guards.
- Bootstrap documentation that explains how the target repository was prepared.

## Migration boundaries

PatchHarbor must stay repository-agnostic.

The migration must not store contributor-specific local paths, user names, private email addresses, workstation names, or source-machine details in tracked files.

Source and target repositories are provided by environment variables or by the caller's current repository context. Scripts should validate both repositories before making changes.

RepoDossier remains unchanged during the target skeleton phase. It should later keep only thin wrappers or configuration where compatibility is needed.

## Next migration step

The next step is to extract one small Dev-Script component into PatchHarbor.

Recommended order:

1. Choose a small helper with clear tests.
2. Copy only the reusable core behavior.
3. Replace project-specific naming with configuration.
4. Add PatchHarbor tests before adoption.
5. Leave source-repository wrappers in place until the new tool is proven.
