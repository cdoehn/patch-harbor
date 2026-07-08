# PatchHarbor Target Bootstrap

PatchHarbor is the separate target repository for repository-agnostic development tools and patch workflow utilities.

This initial bootstrap step intentionally does only a small amount of work:

- prove that the target path is a standalone Git repository
- create one neutral migration note
- keep the RepoDossier source repository unchanged
- avoid copying RepoDossier development scripts before extraction boundaries are tested

Current boundary:

- RepoDossier remains the source repository for the existing development scripts.
- PatchHarbor is the target repository for future generalized tools.
- Follow-up commits add project metadata, a package skeleton, tests, and then extracted tools in small steps.

Safety rules:

- do not store contributor-specific local paths, private names, private e-mail addresses, or machine names in tracked files
- do not treat RepoDossier itself as the target repository
- do not overwrite unrelated existing repositories during migration
- keep compatibility wrappers in RepoDossier until PatchHarbor replacements are tested
